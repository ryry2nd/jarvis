from rake_nltk import Rake
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.llms import GPT4All
from chromadb.config import Settings
from constants import EMBEDDINGS_MODEL_NAME, PORT
import speech_recognition as sr
import pyttsx3, json, os, socket

r = sr.Recognizer()
voice = pyttsx3.init()
keyword = Rake()

wake_word = None
qa = None
show_sources = None

def load(profile='default'):
    global wake_word, qa, show_sources
    dir = os.path.join("aiProfiles", profile)
    with open(os.path.join(dir, "config.json"), 'r') as f:
        config = json.load(f)

    model_path = "models/" + config["model"]
    wake_word = config["name"]
    show_sources = config["debug"]
    persist_directory = os.path.join(dir, "db")
    chroma_settings = Settings(
        chroma_db_impl='duckdb+parquet',
        persist_directory=persist_directory,
        anonymized_telemetry=False
    )

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL_NAME)
    db = Chroma(persist_directory=persist_directory, embedding_function=embeddings, client_settings=chroma_settings)
    retriever = db.as_retriever(search_kwargs={"k": config["target_source_chunks"]})

    # Prepare the LLM
    llm = GPT4All(model=model_path, n_threads=config["n_threads"], verbose=False, n_ctx=config["n_ctx"])

    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=show_sources)

def main():
    #load("jarvis")
    s = socket.socket()
    s.bind(('', PORT))
    s.listen(5)

    while True:
        c , addr = s.accept()
        
        c.send('test'.encode())

        c.close()
    

if __name__ == '__main__':
    main()