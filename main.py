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
        f.close()

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
        c.send(wake_word.encode())
        while True:#codes, 0=nothing, 1=q%a, 2=load, 3=list
            query = pickle.loads(c.recv(1024))
            if query[0] == 0:
                pass
            elif query[0] == 1:
                res = qa(query[1])
                answer = res['result']
                c.send(answer.encode())
                
                if show_sources:
                    print(res['source_documents'])
            elif query[0] == 2:
                if os.path.exists(os.path.join("aiProfiles", query[1])):
                    x = load(query[1])
                    wake_word = x[0]
                    qa = x[1]
                    show_sources = x[2]
                    c.send(wake_word.encode())
                else:
                    c.send("".encode())
            elif query[0] == 3:
                c.send((', '.join(os.listdir("aiProfiles"))).encode())
    except ConnectionResetError:
        pass
    except ConnectionAbortedError:
        pass
    except TimeoutError:
        pass
    except EOFError:
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
        c.settimeout(60)
        
        threads.append(threading.Thread(target=client, args=(c,)))
        threads[-1].start()

if __name__ == '__main__':
    main()