from aiogram import Bot, Dispatcher, executor, types
from requests import get
from time import ctime, sleep
import matplotlib.pyplot as plt
from os import remove, environ


class CurrencyBot:
    API_TOKEN = environ["TOKEN"]
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher(bot)
    working_state = "Stop"
    list_interval = [_ for _ in range(0, 60, 6)]

    @dp.message_handler(commands="start")
    async def greeting(message: types.Message):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="Start", callback_data="start"))
        keyboard.add(types.InlineKeyboardButton(text="Stop", callback_data="stop"))
        await message.answer("Hello! Please, choose button:", reply_markup=keyboard)

    @dp.callback_query_handler(text="start")
    async def start(call: types.CallbackQuery):
        CurrencyBot.working_state = "Start"
        response = get("https://coinpay.org.ua/api/v1/exchange_rate").json()

        lst_of_currency_pair_name = [pair["pair"] for pair in response["rates"]]
        markup = types.ReplyKeyboardMarkup()
        [markup.add(types.KeyboardButton(pair)) for pair in lst_of_currency_pair_name]
        await call.message.answer("Please, select currency pair!", reply_markup=markup)

    @dp.callback_query_handler(text="stop")
    async def stop(call: types.CallbackQuery):

        CurrencyBot.working_state = "Stop"
        await call.message.answer(
            "Please, click /start for restart!",
            reply_markup=types.ReplyKeyboardRemove(),
        )

    @dp.message_handler()
    async def main(message: types.Message):
        response = get("https://coinpay.org.ua/api/v1/exchange_rate").json()
        lst_of_currency_pair_name = [pair["pair"] for pair in response["rates"]]

        if message.text in lst_of_currency_pair_name:
            await message.answer("All is ok, please wait!")

            while CurrencyBot.working_state == "Start":
                lst_prices = []
                current_time = ctime()
                for i in range(10):

                    response = get("https://coinpay.org.ua/api/v1/exchange_rate").json()
                    lst_prices.append(
                        *[
                            i["base_currency_price"]
                            for i in response["rates"]
                            if i["pair"] == message.text
                        ]
                    )
                    sleep(6)

                plt.plot(CurrencyBot.list_interval, lst_prices)
                plt.title(f"{message.text}_{current_time}")
                file_name = f"{current_time}_saved_figure.png"
                plt.savefig(file_name)
                plt.cla()
                photo = types.InputFile(file_name)
                remove(file_name)

                await CurrencyBot.bot.send_photo(chat_id=message.chat.id, photo=photo)

        else:
            await message.answer("Incorrect message, again please!")


if __name__ == "__main__":
    currency_bot = CurrencyBot()
    executor.start_polling(currency_bot.dp, skip_updates=True)
