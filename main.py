from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.llms import GPT4All
from chromadb.config import Settings
from constants import EMBEDDINGS_MODEL_NAME, PORT
import json, os, socket, threading, pickle

def load(profile='default'):
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

    return (wake_word, qa, show_sources)

def client(c: socket.socket):
    try:
        wake_word, qa, show_sources = load(c.recv(1024).decode())
        c.sendall(pickle.dumps((wake_word, show_sources)))
        while True:
            res = qa(c.recv(1024).decode())
            answer = res['result']
            c.send(answer.encode())
            
            if show_sources:
                docs = res['source_documents']
                c.send(docs.encode())
    except ConnectionResetError:
        pass
    except ConnectionAbortedError:
        pass
    except Exception as e:
        print(e)
    c.close()

def main():
    s = socket.socket()
    s.bind(('', PORT))
    s.listen(5)

    threads = []
    print("server started")

    while True:
        c , addr = s.accept()
        
        threads.append(threading.Thread(target=client, args=(c,)))
        threads[-1].start()

if __name__ == '__main__':
    main()