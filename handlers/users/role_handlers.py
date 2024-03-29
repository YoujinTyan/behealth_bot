from keyboards.inline.inline_keyboards import SimpleKeyboardBuilder
from keyboards.default.default_keyboards import MenuKeyboardBuilder
from keyboards.default.default_keyboards import BACK_BUTTONS_TEXTS
from data.config import ROLE_COMMANDS, ROLES, ROLE_NAMES
from states.states import StateGroup, RoleStates
from aiogram.types import ReplyKeyboardRemove
from loader import dp, bot, postgres_manager
from aiogram.dispatcher import FSMContext
from aiogram import types

# --------------------------------------CONSULTANT HANDLERS -----------------------------------------------

greeting_consultant_message = """
Теперь вы стали консультантом !
"""

consultant_instructions_message = """
Инструкция: Ожидайте сообщений от пациентов. 

Чтобы ответить, делайте обязательно reply на сообщение, на которое хотите ответить. 
Тогда я смогу переслать его нужному пациенту. 
Чтобы перестать быть консультантом, напишите !&consultoff
"""

reply_instruction = """
Чтобы сделать reply, смахните сообщение пациента влево.
"""


# ----------------------------CONSULTANT SIDE-------------------

def filter_consultant_commands(message: types.Message):
    if ROLE_COMMANDS["consultant_on"] == message.text:
        return True
    elif ROLE_COMMANDS["consultant_off"] == message.text:
        return True

    return False


@dp.message_handler(filter_consultant_commands, state="*")
async def handle_get_consult_role_command(message: types.Message, state: FSMContext):
    if message.text == ROLE_COMMANDS["consultant_on"]:
        if bool(await postgres_manager.get_current_consultant()):
            consult_menu_keyboard = MenuKeyboardBuilder().get_consultant_menu()
            await postgres_manager.change_user_role(user=message.from_user, new_role=ROLE_NAMES["consultant"])
            await message.answer(greeting_consultant_message, reply_markup=ReplyKeyboardRemove())
            await message.answer(consultant_instructions_message)
            await message.answer(reply_instruction, reply_markup=consult_menu_keyboard)

            await state.finish()
            await RoleStates.is_consultant.set()

        else:
            await message.answer("Уже имеется действующий консультант!")

    elif message.text == ROLE_COMMANDS["consultant_off"]:
        await postgres_manager.change_user_role(message.from_user, ROLE_NAMES["user"])
        await message.answer("Теперь вы не консультант!", reply_markup=SimpleKeyboardBuilder.get_back_to_menu_keyboard())
        await state.finish()


@dp.message_handler(state=RoleStates.is_consultant)
async def handle_consultant_messages(message: types.Message):
    print('handle_consultant_messages started')
    print(message["reply_to_message"])
    if message["reply_to_message"] is not None:
        start_index = message.reply_to_message.text.find("ID:") + len("ID:")
        user_id = int(message.reply_to_message.text[start_index:])
        cut_off_index = message.reply_to_message.text.find("\nОт пациента\nУИК:")
        print(f'send to {user_id}. Message: {message.text}')
        print(f'send from {message.reply_to_message.text[:cut_off_index]}')

        await bot.send_message(
            chat_id=user_id,
            text=f"Ответ консультанта на сообщение:\n{message.reply_to_message.text[:cut_off_index]}\n\n{message.text}"
        )

    else:
        await message.answer(consultant_instructions_message)
        await message.answer(reply_instruction)


# ----------------------CLIENT SIDE-------------------------
async def rate_consultant(message: types.Message):
    rate_consultant_keyboard = SimpleKeyboardBuilder.get_rate_consultant_keyboard()
    rate_consultant_text = "Спасибо за обращение! Оцените, пожалуйста, работу консультанта."
    await message.answer(rate_consultant_text, reply_markup=rate_consultant_keyboard)


async def open_menu(message: types.Message):
    await message.delete()
    await message.answer("Меню", reply_markup=MenuKeyboardBuilder().get_main_menu_keyboard(message.from_user))


async def get_current_consultant():
    consultant = await postgres_manager.get_current_consultant()
    if bool(consultant) is False:
        consultant = ROLES["consultant"]
        return consultant

    else:
        return consultant["user_id"]


async def send_message_to_consultant(message: types.Message):
    consultant = await get_current_consultant()
    user_uik = await postgres_manager.get_user_uik(message.from_user)
    from_user = f"От пациента\nУИК: {user_uik}\nID: {message.from_user.id}\n"

    await bot.send_message(
        text=f"{message.text}\n\n{from_user}",
        chat_id=consultant
    )


async def send_end_conversation_message_to_consultant(message: types.Message):
    consultant = await get_current_consultant()
    user_uik = await postgres_manager.get_user_uik(message.from_user)
    quit_message = f"Пациент {user_uik}\nЗавершил общение!"

    await bot.send_message(
        text=quit_message,
        chat_id=consultant
    )


@dp.message_handler(state=StateGroup.in_consult)
async def handle_consultant_conversation(message: types.Message, state: FSMContext):
    if message.text == BACK_BUTTONS_TEXTS['end_conversation']:
        await send_end_conversation_message_to_consultant(message)
        if not await postgres_manager.is_consultant_rated(message.from_user):
            await rate_consultant(message)

        else:
            await open_menu(message)
        await state.finish()

    else:
        await send_message_to_consultant(message)


@dp.callback_query_handler(lambda call: "star_" in call.data)
async def handle_consultant_rating(call: types.CallbackQuery):
    await postgres_manager.rate_consultant(call.from_user, rate=int(call.data.replace("star_", "")))
    await open_menu(call.message)

