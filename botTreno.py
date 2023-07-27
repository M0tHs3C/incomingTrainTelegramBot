import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
import requests
from datetime import datetime,timedelta
import pytz
import time
import json
import urllib.parse

SELECTING_STATION, IN_LOOP = range(2)
timezone = pytz.timezone('Europe/Rome')
user_preferences = {}
train_arrived = {}
def start(update, context):
    pytz.timezone('Europe/Rome')
    user_id = update.effective_user.id
    if user_id in user_preferences:
        update.message.reply_text("Hai già avviato il bot. Puoi utilizzare /stop per fermarlo.")
        return ConversationHandler.END
    else:
        update.message.reply_text("Benvenuto!\nPer iniziare, mandami la stazione che vuoi controllare:")
        return SELECTING_STATION

def stop(update, context):
    user_id = update.effective_user.id
    if user_id in user_preferences:
        del user_preferences[user_id]
        update.message.reply_text("Il bot è stato fermato.")
    else:
        update.message.reply_text("Il bot non è attivo. Puoi utilizzare /start per avviarlo.")
    return ConversationHandler.END

def select_station(update, context):
    user_id = update.effective_user.id
    station = update.message.text
    user_preferences[user_id] = station
    update.message.reply_text(f"Hai selezionato la stazione: {station}.\nIl bot inizierà ad inviare messaggi ogni 30 secondi. Utilizza /stop per fermarlo.")
    context.job_queue.run_repeating(send_message, interval=2, first=0, context=user_id)
    return IN_LOOP

def send_message(context):
    job = context.job
    user_id = job.context
    station = user_preferences.get(user_id)
    if station:
        url= "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno/autocompletaStazione/"+station
        response = requests.get(url)
        stringa = response.content.decode('utf-8')
        stringaSpezzata = stringa.split("|")
        if len(stringaSpezzata) == 2:
            codiceStazione = stringaSpezzata[1]
        else:
            codiceStazione = "errore"
        if codiceStazione:
            current_date = datetime.now()
            formatted_date = current_date.strftime("%a %b %d %Y %H:%M:%S")
            treni_in_arrivo = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno/arrivi/"+codiceStazione.replace("\n","")+"/"+urllib.parse.quote(formatted_date)
            r = requests.get(treni_in_arrivo)
            if r.status_code == 200:
                treni = json.loads(r.content)
                for treno in treni:
                    if treno['inStazione'] == False and treno['circolante'] == True:
                        data_arrivo_comp = treno['compOrarioArrivo']
                        ora_arrivo = datetime.strptime(data_arrivo_comp, '%H:%M')
                        ora_arrivo = current_date.strftime("%Y-%m-%d") + ' '+ treno['compOrarioArrivo']
                        ora_arrivo = datetime.strptime(ora_arrivo, '%Y-%m-%d %H:%M')
                        if ora_arrivo >= current_date:
                            if under_30_secs(ora_arrivo,current_date):
                                if treno['numeroTreno'] not in train_arrived[user_id]:
                                    train_arrived[user_id] = treno['numeroTreno']
                                    context.bot.send_message(user_id, f"Sta arrivando il treno {treno['compNumeroTreno']} delle {treno['compOrarioArrivo']} da {treno['origine']} ")
        else:
            job.schedule_removal()


def under_30_secs(data_arrivo, data_attuale):
    diff = data_arrivo - data_attuale
    trenta_secondi = timedelta(seconds=30)
    if diff <= trenta_secondi:
        return True
    else:
        return False
def elimina_ultime_tre_cifre(numero):
    numero_str = str(numero)
    if len(numero_str) > 10:
        numero_str_senza_ultime_tre_cifre = numero_str[:-3]
        risultato = int(numero_str_senza_ultime_tre_cifre)
        return risultato
    else:
        return numero


def main():
    token = "INSERT_TOKEN_HERE"
    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_STATION: [MessageHandler(Filters.text & ~Filters.command, select_station)],
            IN_LOOP: [CommandHandler('stop', stop)],
        },
        fallbacks=[],
    )
    dispatcher.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
