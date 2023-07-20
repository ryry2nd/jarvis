import os
os.add_dll_directory(os.getcwd())

from speech_recognition.exceptions import UnknownValueError
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from rake_nltk import Rake
from constants import IP, PORT, MEDIA_QUALITIES
from youtube_search import YoutubeSearch
import speech_recognition as sr
import pyttsx3, socket, pickle, time, random, vlc, yt_dlp

r = sr.Recognizer()
voice = pyttsx3.init()
keyword = Rake()

instance = vlc.Instance('--no-xlib -q > /dev/null 2>&1')
player = instance.media_player_new()

def generate_stream_url(URL):
    ydl_opts = {"quiet":True }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(URL, download=False)
        url_list = []
        counter = -1
        for format in info['formats']:
            video_format = format['format']
            video_format_short = video_format[video_format.find("(")+1:video_format.find(")")] 
            if (video_format[2]==" " or "audio only" in video_format) and not("DASH" in video_format) and not(counter > -1 and video_format_short == url_list[counter]['video_format']):
                url_list.append({
                        'stream_url':format['url'],
                        'video_format':video_format_short
                        })
                counter +=1

    break_out_flag = False
    for index in range(2):
        if break_out_flag:
            break
        for item in url_list:
            if item['video_format'] == MEDIA_QUALITIES[2-index]:
                url = item['stream_url']
                break_out_flag = True
                break
    return url

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
    s = socket.socket()

    s.connect((IP, PORT))

    s.send("jarvis".encode())

    wake_word = s.recv(1024).decode()

    driver = webdriver.Chrome()
    driver.implicitly_wait(0.6)

    say(wake_word + " activated")

    while True:#codes, 0=nothing, 1=q%a, 2=load, 3=list
        s.send(pickle.dumps((0, )))
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
                        player.pause()
                    elif isKeyword("spell"):
                        answer = '-'.join([*(' '.join(queryList[getWordIndex(queryList, "spell")+1:]))])
                    elif isKeyword("say"):
                        answer = ' '.join(queryList[getWordIndex(queryList, "say")+1:])
                    elif isKeyword("fart") or isKeyword("farts"):
                        dir = "fart_noise_library/" + random.choice(os.listdir("fart_noise_library"))
                        player.set_media(vlc.Media(dir))
                        player.play()
                    elif isKeyword("restart") or isKeyword("reboot"):
                        driver.quit()
                        driver = webdriver.Chrome()
                        driver.implicitly_wait(0.6)
                    elif isKeyword("play"):
                        i = getWordIndex(queryList, "play")

                        if len(queryList[i+1:]) != 0:
                            results = YoutubeSearch(' '.join(queryList[i+1:]), max_results=1).to_dict()
                            player.set_media(instance.media_new(generate_stream_url("https://www.youtube.com/watch?v=" + results[0]['id'])))
                            player.play()
                        else:
                            player.pause()
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
                                s.close()
                                time.sleep(1)
                                say("system offline")
                                return
                            elif ans == "no" or ans == "nah":
                                break
                            else:
                                say("this is serious, Yes or No")
                    elif isKeyword("profiles") and isKeyword("list"):
                        answer = "the list of profiles are: "
                        s.send(pickle.dumps((3, )))
                        answer += s.recv(1024).decode()
                    elif isKeyword("switch") or isKeyword("profile") or isKeyword("profiles"):
                        mn = max(getWordIndex(queryList, "switch"), getWordIndex(queryList, "to"), getWordIndex(queryList, "the"))
                        if queryList[-1] == "profile":
                            mx = len(queryList)-1
                        else:
                            mx = len(queryList)
                        
                        pro = '_'.join(queryList[mn+1:mx])
                        
                        s.send(pickle.dumps((2, pro)))

                        ret = s.recv(1024).decode()

                        if ret:
                            wake_word = ret
                            answer = "profile successfully switched to the " + pro + " profile"
                            answer += ", the wake word is now: " + wake_word
                        else:
                            answer = "profile " + pro + " does not exist"
                    else:
                        s.send(pickle.dumps((1, query)))
                        answer = s.recv(1024).decode()
                except Exception as e:
                    answer = e
                    print(e)

                say(answer)

if __name__ == '__main__':
    main()