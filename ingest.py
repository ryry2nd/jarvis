import os
import glob, argparse, json, shutil, errno
from typing import List
from multiprocessing import Pool
from constants import EMBEDDINGS_MODEL_NAME
from tqdm import tqdm

from langchain.document_loaders import (
    PyMuPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
)
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document

chunk_size = 500
chunk_overlap = 50

# Map file extensions to document loaders and their arguments
LOADER_MAPPING = {
    ".html": (UnstructuredHTMLLoader, {}),
    ".md": (UnstructuredMarkdownLoader, {}),
    ".pdf": (PyMuPDFLoader, {}),
    ".txt": (TextLoader, {"encoding": "utf8"}),
}


def load_single_document(file_path: str) -> List[Document]:
    ext = "." + file_path.rsplit(".", 1)[-1]
    if ext in LOADER_MAPPING:
        loader_class, loader_args = LOADER_MAPPING[ext]
        loader = loader_class(file_path, **loader_args)
        return loader.load()

    raise ValueError(f"Unsupported file extension '{ext}'")

def load_documents(source_dir: str, ignored_files: List[str] = []) -> List[Document]:
    """
    Loads all documents from the source documents directory, ignoring specified files
    """
    all_files = []
    for ext in LOADER_MAPPING:
        all_files.extend(
            glob.glob(os.path.join(source_dir, f"**/*{ext}"), recursive=True)
        )
    filtered_files = [file_path for file_path in all_files if file_path not in ignored_files]

    with Pool(processes=os.cpu_count()) as pool:
        results = []
        with tqdm(total=len(filtered_files), desc='Loading new documents', ncols=80) as pbar:
            for i, docs in enumerate(pool.imap_unordered(load_single_document, filtered_files)):
                results.extend(docs)
                pbar.update()

    return results

def process_documents(source_directory: str, ignored_files: List[str] = []) -> List[Document]:
    """
    Load documents and split in chunks
    """
    print(f"Loading documents from {source_directory}")
    documents = load_documents(source_directory, ignored_files)
    if not documents:
        print("No new documents to load")
        exit(0)
    print(f"Loaded {len(documents)} new documents from {source_directory}")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    texts = text_splitter.split_documents(documents)
    print(f"Split into {len(texts)} chunks of text (max. {chunk_size} tokens each)")
    return texts

def does_vectorstore_exist(persist_directory: str) -> bool:
    """
    Checks if vectorstore exists
    """
    if os.path.exists(os.path.join(persist_directory, 'index')):
        if os.path.exists(os.path.join(persist_directory, 'chroma-collections.parquet')) and os.path.exists(os.path.join(persist_directory, 'chroma-embeddings.parquet')):
            list_index_files = glob.glob(os.path.join(persist_directory, 'index/*.bin'))
            list_index_files += glob.glob(os.path.join(persist_directory, 'index/*.pkl'))
            # At least 3 documents are needed in a working vectorstore
            if len(list_index_files) > 3:
                return True
    return False

def main():
    # Create embeddings
    dest = os.path.join("aiProfiles", parse())
    persist_directory = os.path.join(dest, "db")
    source_directory = os.path.join(dest, "source_documents")
    with open(os.path.join(dest, "config.json"), 'r') as f:
        config = json.load(f)
        collect_default = config["collect_from_default"]

    chroma_settings = Settings(
        chroma_db_impl='duckdb+parquet',
        persist_directory=persist_directory,
        anonymized_telemetry=False
    )
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL_NAME)

    if does_vectorstore_exist(persist_directory):
        # Update and store locally vectorstore
        print(f"Appending to existing vectorstore at {persist_directory}")
        db = Chroma(persist_directory=persist_directory, embedding_function=embeddings, client_settings=chroma_settings)
        collection = db.get()
        texts = process_documents(source_directory, [metadata['source'] for metadata in collection['metadatas']])
        
        if collect_default:
            def_source_directory = os.path.join("aiProfiles", "default", "source_documents")
            dTexts = process_documents(def_source_directory, [metadata['source'] for metadata in collection['metadatas']])
            db.add_documents(dTexts)
        print(f"Creating embeddings. May take some minutes...")
        db.add_documents(texts)
    else:
        # Create and store locally vectorstore
        if collect_default:
            src = os.path.join("aiProfiles", "default", "db")
            try:
                shutil.copytree(src, persist_directory)
            except OSError as exc:
                if exc.errno in (errno.ENOTDIR, errno.EINVAL):
                    shutil.copy(src, dest)
                else: raise
            db = Chroma(persist_directory=persist_directory, embedding_function=embeddings, client_settings=chroma_settings)
            texts = process_documents(source_directory)
            db.add_documents(texts)
        else:
            print("Creating new vectorstore")
            texts = process_documents(source_directory)
            print(f"Creating embeddings. May take some minutes...")
            db = Chroma.from_documents(texts, embeddings, persist_directory=persist_directory, client_settings=chroma_settings)
    db.persist()
    db = None

def parse():
    parser = argparse.ArgumentParser(description="make database",
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-d", "--dest", help="Destination location")
    args = parser.parse_args()
    config = vars(args)
    return config.get("dest")

if __name__ == "__main__":
    main()
