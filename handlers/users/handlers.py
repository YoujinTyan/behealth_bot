from utils.db_api.db_api import PostgresDataBaseManager, DataConvertor, DB_USERS_COLUMNS
from keyboards.default.default_keyboards import MENU_BUTTONS_TEXTS, MenuKeyboardBuilder
from keyboards.inline.inline_keyboards import SimpleKeyboardBuilder, TestKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from data.tests.test_manager import HivRiskAssessment, TESTS_LANGUAGES_CALLBACKS
from utils.db_api.connection_configs import ConnectionConfig
from aiogram.dispatcher import FSMContext
from states.states import StateGroup
from loader import dp, bot
from aiogram import types


@dp.callback_query_handler(lambda callback: callback.data == 'menu')
async def start_menu(callback_query: types.CallbackQuery):
    menu_keyboard = MenuKeyboardBuilder().get_keyboard(callback_query.from_user)
    await callback_query.message.answer('Меню', reply_markup=menu_keyboard)
    await callback_query.message.delete()


@dp.message_handler(lambda message: message.text in MENU_BUTTONS_TEXTS.values())
async def handle_menu_buttons(message: types.Message):
    if message.text == MENU_BUTTONS_TEXTS["hiv_risk_assessment"]:
        ru_button = InlineKeyboardButton(text="Русский", callback_data="ru_hiv_risk_assessment")
        kz_button = InlineKeyboardButton(text="Қазақша", callback_data="kz_hiv_risk_assessment")
        language_select_keyboard = InlineKeyboardMarkup(row_width=1).add(ru_button, kz_button)
        await message.answer("Выберите язык, чтобы продолжить:", reply_markup=language_select_keyboard)
        await message.answer("Меню скрыто!", reply_markup=ReplyKeyboardRemove())
        await StateGroup.in_hiv_risk_assessment.set()

    elif message.text == MENU_BUTTONS_TEXTS["info_files"]:
        product = SimpleKeyboardBuilder.get_language_selection_documents_keyboard()
        await message.answer(text=product["text"], reply_markup=product["keyboard"])

    elif message.text == MENU_BUTTONS_TEXTS["order_vih_test"]:
        # Это все равно временный вариант, до того как мы не сделаем работу с API
        btn = InlineKeyboardButton("Перейти", url="https://hivtest.kz/")
        await message.answer('Заказать бесплатный тест', reply_markup=InlineKeyboardMarkup().add(btn))

    elif message.text == MENU_BUTTONS_TEXTS["tell_partner"]:
        product = SimpleKeyboardBuilder.get_tell_partner_keyboard()
        await message.answer(text=product["text"], reply_markup=product["keyboard"])

    elif message.text == MENU_BUTTONS_TEXTS["project_news"]:
        product = SimpleKeyboardBuilder.get_project_news_keyboards()
        await message.answer(text=product[0]["text"], reply_markup=product[0]["keyboard"])
        await message.answer(text=product[1]["text"], reply_markup=product[1]["keyboard"])

    elif message.text == MENU_BUTTONS_TEXTS["social_networks"]:
        product = SimpleKeyboardBuilder.get_social_networks_keyboard()
        await message.answer(text=product["text"], reply_markup=product["keyboard"])

    elif message.text == MENU_BUTTONS_TEXTS["get_users"]:
        file_name = "users"

        connection_config = ConnectionConfig().get_postgres_connection_config()
        postgres_manager = PostgresDataBaseManager(connection_config)
        users_data = await postgres_manager.get_all_users()

        data_convertor = DataConvertor()
        saved_file_path = await data_convertor.convert_to_exel(users_data, DB_USERS_COLUMNS, file_name)

        with open(saved_file_path, "rb") as exel_users_data:
            await bot.send_document(chat_id=callback_query.from_user.id, document=exel_users_data)


@dp.callback_query_handler(lambda call: call.data == "send_document_KZ" or call.data == 'send_document_RU')
async def send_info_document(callback_query: types.CallbackQuery):
    if callback_query.data == "send_document_RU":
        await callback_query.message.edit_text("Пару секунд, загружаю информацию...")

        with open("data/info_files/Что такое ДКП ВИЧ.pdf", "rb") as ru_document:
            await bot.send_document(callback_query.from_user.id, document=ru_document)

    elif callback_query.data == "send_document_KZ":
        await callback_query.message.edit_text("Бірнеше секунд, ақпаратты жүктеп салу...")

        with open("data/info_files/КДП дегеніміз не.pdf", "rb") as kz_document:
            await bot.send_document(callback_query.from_user.id, document=kz_document)

    await callback_query.message.delete()


@dp.callback_query_handler(lambda call: call.data in TESTS_LANGUAGES_CALLBACKS, state=StateGroup.in_hiv_risk_assessment)
async def handle_language_selection(call: types.CallbackQuery, state: FSMContext):
    test_keyboard_builder = TestKeyboardBuilder()
    test_materials = HivRiskAssessment().get_ru_version()

    if "hiv_risk_assessment" in call.data:
        if call.data.startswith("ru"):
            test_materials = HivRiskAssessment().get_ru_version()

        elif call.data.startswith("kz"):
            test_materials = HivRiskAssessment().get_kz_version()

        keyboards = test_keyboard_builder.get_keyboards(test_materials=test_materials)
        async with state.proxy() as state_memory:
            state_memory["keyboards"] = keyboards
            state_memory['score'] = 0
            state_memory["question_number"] = 1
            state_memory["risks"] = test_materials["risk_ratings"]

        await call.message.answer(keyboards["question_1"]["text"], reply_markup=keyboards["question_1"]["keyboard"])
        await call.message.delete()

    # elif другой тест:
    #     pass

# ---------------------------TESTS HANDLERS-----------------------------------------------


@dp.callback_query_handler(state=StateGroup.in_hiv_risk_assessment)
async def handle_hiv_risk_assessment(call: types.CallbackQuery, state: FSMContext):

    async with state.proxy() as state_memory:
        state_memory["score"] += int(call.data)
        state_memory["question_number"] += 1

        score = state_memory["score"]
        keyboards = state_memory["keyboards"]
        question_number = state_memory["question_number"]
        risks = state_memory["risks"]

    high_risk = risks["high"]
    medium_risk = risks["medium"]
    small_risk = risks['small']

    if question_number == len(keyboards):
        await state.finish()
        back_to_menu = SimpleKeyboardBuilder.get_back_to_menu_keyboard()

        if score >= 22:
            await call.message.answer(text=high_risk, reply_markup=back_to_menu)
            await call.message.delete()

        elif 21 >= score >= 7:
            await call.message.answer(text=medium_risk, reply_markup=back_to_menu)
            await call.message.delete()

        elif score < 7:
            await call.message.answer(text=small_risk, reply_markup=back_to_menu)
            await call.message.delete()

    else:
        await call.message.delete()
        await call.message.answer\
            (
                text=keyboards[f"question_{question_number}"]["text"],
                reply_markup=keyboards[f"question_{question_number}"]["keyboard"]
            )


# @dp.callback_query_handler(state=StateGroup.test2)
# async def handle_test2(call: types.CallbackQuery, state: FSMContext):
#     pass
#
#
# @dp.callback_query_handler(state=StateGroup.test3)
# async def handle_test3(call: types.CallbackQuery, state: FSMContext):
#     pass
#
#
# @dp.callback_query_handler(state=StateGroup.test4)
# async def handle_test4(call: types.CallbackQuery, state: FSMContext):
#     pass
#
#
# @dp.callback_query_handler(state=StateGroup.test5)
# async def handle_test5(call: types.CallbackQuery, state: FSMContext):
#     pass