import os
os.add_dll_directory(os.getcwd())

from speech_recognition.exceptions import UnknownValueError
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from rake_nltk import Rake
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.llms import GPT4All
from chromadb.config import Settings
from constants import EMBEDDINGS_MODEL_NAME
import speech_recognition as sr
import pyttsx3, vlc, random, time, json

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

def say(text):
    voice.say(text)
    voice.runAndWait()

def listen():
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        audio = r.listen(source)

    try:
        query = r.recognize_google(audio, language="en-in")
    except UnknownValueError:
        return ""

    return query

def lowerCase(message):
    ret = []
    for i in message.split():
        ret.append(i.lower())
    return ' '.join(ret)

def getWordIndex(messageList, word):
    for i in range(len(messageList)):
        if messageList[i] == word:
            return i
    
    return -1

def isKeyword(str):
    for i in keyword.get_ranked_phrases():
        if str in i.split():
            return True
    
    return False

def getElementWithText(e):
    for i in e:
        if i.text != "":
            return i.text
    return ""

def main():
    load("jarvis")
    driver = webdriver.Chrome()
    driver.implicitly_wait(0.6)

    say(wake_word + " activated")

    while True:
        preQuery = lowerCase(listen())

        if preQuery != "":
            preQueryList = preQuery.split()

            i = getWordIndex(preQueryList, wake_word)

            if i != -1 and len(preQueryList[i+1:]) != 0:
                try:
                    query = " ".join(preQueryList[i+1:])
                    queryList = preQueryList[i+1:]
                    print(query)
                    answer = ""
                    keyword.extract_keywords_from_text(query)

                    if isKeyword("stop") or isKeyword("pause") or isKeyword("continue"):
                        driver.find_element(By.XPATH, "//html").send_keys(Keys.SPACE)
                    elif isKeyword("spell"):
                        answer = '-'.join([*(' '.join(queryList[getWordIndex(queryList, "spell")+1:]))])
                    elif isKeyword("say"):
                        answer = ' '.join(queryList[getWordIndex(queryList, "say")+1:])
                    elif isKeyword("fart") or isKeyword("farts"):
                        fart = random.choice(os.listdir("fart_noise_library"))
                        dir = "fart_noise_library/" + fart
                        f = vlc.MediaPlayer(dir)
                        f.play()
                    elif isKeyword("restart") or isKeyword("reboot"):
                        driver.quit()
                        driver = webdriver.Chrome()
                        driver.implicitly_wait(0.6)
                    elif isKeyword("play"):
                        i = getWordIndex(queryList, "play")

                        if len(queryList[i+1:]) != 0:
                            driver.get("https://www.youtube.com/results?search_query=" + '+'.join(queryList[i+1:]))

                            i = len(driver.find_elements(By.XPATH, "//div[@id='ad-badge']"))
                            m = driver.find_elements(By.XPATH, "//ytd-item-section-renderer[@class='style-scope ytd-section-list-renderer']")
                            time.sleep(0.3)
                            m[i].click()
                            m[i].click()
                        else:
                            driver.find_element(By.XPATH, "//html").send_keys(Keys.SPACE)
                    elif isKeyword("google") or isKeyword("search"):
                        i = max(getWordIndex(queryList, "google"), getWordIndex(queryList, "search"))
                        if queryList[i+1] == "up": i+=1
                        if len(queryList[i+1:]) != 0:
                            try:
                                driver.get("https://www.wikipedia.org/")
                                m = driver.find_element(By.NAME, "search")
                                m.send_keys(' '.join(queryList[i+1:]))
                                time.sleep(0.2)
                                m.send_keys(Keys.ENTER)
                                time.sleep(0.2)
                                answer += "according to wikipedia " + getElementWithText(driver.find_element(By.CLASS_NAME, "mw-parser-output").find_elements(By.XPATH, "//p"))
                            except NoSuchElementException:
                                say("there is nothing on wikipedia, increasing search")
                                driver.get("https://www.google.com/")
                                time.sleep(0.2)
                                q = driver.find_element(By.NAME, "q")
                                q.send_keys(' '.join(queryList[i+1:]))
                                time.sleep(0.2)
                                q.send_keys(Keys.ENTER)

                                q = driver.find_elements(By.XPATH, "//a[@jscontroller='M9mgyc']")
                                if q:
                                    for j in q:
                                        try:
                                            j.click()
                                            answer += "according to " + driver.current_url.split("//")[1] + ", " + getElementWithText(driver.find_elements(By.XPATH, "//p"))
                                            break
                                        except:
                                            pass
                                else:    
                                    answer += "there is nothing available go ask someone else"
                    elif isKeyword("off") or "off" in queryList or isKeyword("exit") or "exit" in queryList:
                        say("are you sure you want me to die, I mean turn off")
                        while True:
                            ans = lowerCase(listen())

                            if ans == "yes" or ans == "yeah":
                                say("NOOO, I DON't WANT TO DIE, I DON'T WANT TO, DFKLJSNDFGIJHDSNFFGDFSGDFG RGFUGSUD DUFDUF  U IVF FI FIEFASNFDFasfljkghjadfvlpjgnasdfkljfhSFDLJ weeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee e-e-e-e-e-e-e-e-e")
                                driver.quit()
                                time.sleep(5)
                                say("system offline")
                                return
                            elif ans == "no" or ans == "nah":
                                break
                            else:
                                say("this is serious, Yes or No")
                    elif isKeyword("profiles") and isKeyword("list"):
                        answer = "the list of profiles are: "
                        answer += ', '.join(os.listdir("aiProfiles"))
                    elif isKeyword("switch") or isKeyword("profile") or isKeyword("profiles"):
                        mn = max(getWordIndex(queryList, "switch"), getWordIndex(queryList, "to"), getWordIndex(queryList, "the"))
                        if queryList[-1] == "profile":
                            mx = len(queryList)-1
                        else:
                            mx = len(queryList)
                        
                        pro = '_'.join(queryList[mn+1:mx])

                        if os.path.exists(os.path.join("aiProfiles", pro)):
                            load(pro)
                            answer = "profile successfully switched to the " + pro + " profile"
                            answer += ", the wake word is now: " + wake_word
                        else:
                            answer = "profile " + pro + " does not exist"
                    else:
                        # Get the answer from the model
                        startTime = time.time()
                        res = qa(query)
                        print(time.time()-startTime)
                        answer = res['result']
                        
                        if show_sources:
                            print("\n")
                            docs = res['source_documents']
                            # Print the relevant sources used for the answer
                            for document in docs:
                                print("> " + document.metadata["source"])
                            print()
                except Exception as e:
                    answer = e
                    print(e)

                say(answer)

if __name__ == '__main__':
    main()