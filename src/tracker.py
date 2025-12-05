import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import text, hbold, hitalic, hlink
from solana.rpc.async_api import AsyncClient
from sqliter import SQLighter
from utils import get_balance_changes, to_sol, get_token_balances, timestamp
from dotenv import load_dotenv
from os import getenv


ENDPOINT = "https://api.mainnet-beta.solana.com"
TX_URL = 'https://explorer.solana.com/tx/%s'
ADDRESS_URL = 'https://explorer.solana.com/address/%s'

logging.basicConfig(level=logging.INFO, filename='bot.log')

load_dotenv()

TOKEN = getenv('BOT_TOKEN')

bot = Bot(token='')
storage = MemoryStorage()

form_router = Router()
db = SQLighter('wallets.db')

class Menu(StatesGroup):
    menu = State()
    add_wallet = State()
    remove_wallet = State()
    see_wallets = State()

@form_router.message(CommandStart())
async def menu(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    new = InlineKeyboardButton('Add wallet', callback_data='add')
    remove = InlineKeyboardButton('Remove wallet', callback_data='remove')
    see = InlineKeyboardButton('See wallets', callback_data='see')
    kb.add(new, remove, see)
    await message.reply('Please, select action', reply_markup=kb)


@form_router.callback_query(lambda query: query.data == 'add')
async def add(query: types.CallbackQuery, state: FSMContext):
    await query.message.answer('Send wallet name and a 44 character sol wallet address, format: "name address"')
    await state.set_state(Menu.add_wallet)
    await query.answer()


@form_router.message(Menu.add_wallet)
async def process_add(message: types.Message):
    wallet = message.text.split()
    if len(wallet) != 2:
        await message.answer('Invalid syntax, should be "name address". Try again:')
        return
    result = await _latest_wallet_tx_sig(wallet[1])
    if 'error' in result:
        await message.answer('Invalid wallet address, try again:')
        return
    if db.wallet_exists(wallet[1], message.chat.id):
        await message.answer('Wallet already added, try again:')
        return
    slot = _get_slot(result)
    db.add_wallet(wallet[0], wallet[1], message.chat.id, slot)
    logging.info(f'Wallet added {wallet[0]}')
    await message.answer('New wallet added!')
    await Menu.menu.set()


@form_router.callback_query(lambda query: query.data == 'remove')
async def del_wallet(query: types.CallbackQuery, state: FSMContext):
    addresses = db.get_tracking_wallets(query.message.chat.id)
    markup = InlineKeyboardMarkup()
    buttons = (InlineKeyboardButton((address[0]), callback_data=address[0]) for address in addresses)
    markup.add(*buttons)
    await state.set_state(Menu.remove_wallet)
    response = 'Tap the wallet you want to remove:'
    await query.message.answer(response, reply_markup=markup)
    await query.answer()


@form_router.message(Menu.remove_wallet)
async def process_del(query: types.CallbackQuery):
    wallet = query.data
    if not db.wallet_exists(wallet, query.message.chat.id):
        await query.message.answer('Wallet not added yet')
        return
    db.delete_wallet(wallet, query.message.chat.id)
    logging.info(f'Wallet deleted {wallet}')
    await query.message.answer('Wallet deleted!')
    await query.answer()
    await query.message.delete()
    await Menu.menu.set()

@form_router.callback_query(lambda query: query.data == 'see')
async def see_wallets(query: types.CallbackQuery):
    addresses = db.get_tracking_wallets(query.message.chat.id)
    result = 'Tracked Wallets:\n\n'
    for address in addresses:
        result += f'{address[0]}:\n{address[1]}\n'
    await query.message.answer(result)
    await query.answer()


async def _latest_wallet_tx_sig(address: str, client: AsyncClient = None):
    if client:
        return await client.get_confirmed_signature_for_address2(address, limit=1)
    async with AsyncClient(ENDPOINT) as client:
        return await client.get_confirmed_signature_for_address2(address, limit=1)


def _get_tx_sig(rpc_result):
    return rpc_result['result'][0]['signature']


def _get_slot(rpc_result):
    return rpc_result['result'][0]['slot']


async def get_tx_info(tx_sig: str, client: AsyncClient = None):
    if client:
        return await client.get_confirmed_transaction(tx_sig)
    async with AsyncClient(ENDPOINT) as client:
        return await client.get_confirmed_transaction(tx_sig)


def form_message(wallet, tx: dict, tx_sig):
    print('Forming notification')
    accounts = tx['transaction']['message']['accountKeys']
    block_time = tx['blockTime']
    print('block time', block_time)
    status = 'Success' if not tx['meta']['err'] else tx['meta']['err']
    fee = f"Transaction fee: {format(to_sol(tx['meta']['fee']), '.6f')} sol"
    block = f"Block: {tx['slot']}"
    balance_changes = get_balance_changes(accounts, tx['meta']['preBalances'], tx['meta']['postBalances'])
    print('balance_changes', balance_changes)
    token_balance_changes = get_token_balances(accounts, tx['meta']['preTokenBalances'],
                                               tx['meta']['postTokenBalances'])
    print('token_balance_changes', token_balance_changes)
    account_inputs = ''
    for account_input in balance_changes:
        address, post_balance, change = account_input
        change = '+' + str(change) if change > 0 else change
        account_inputs += f'{hlink(address, ADDRESS_URL % address)} | Balance: {post_balance} (change: {change}) sol\n'
        account_inputs += '~~~~~~~~~~~~~~~~~~~~~\n'

    token_balances = ''
    if token_balance_changes:
        for el in token_balance_changes:
            address, token, amount, change = el
            change = '+' + str(change) if change > 0 else change
            token_balances += f'{hlink(address, ADDRESS_URL % address)} | token={hlink(token, ADDRESS_URL % token)} | change {change} | Post Balance {amount}\n'
            token_balances += '~~~~~~~~~~~~~~~~~~~~~\n'
        token_balances = text(hbold('Token balances:\n'), token_balances)

    if len(accounts) == 3:
        header = 'New Transfer!'
    elif not tx['meta']['preTokenBalances'] and tx['meta']['postTokenBalances']:
        header = 'Token Mint'
    else:
        header = 'New Transaction'
    header = hlink(header, TX_URL % tx_sig)
    message = text(f'Wallet tracked: {hlink(wallet[3], ADDRESS_URL % wallet[0])}', header, hitalic(f'Status: {status}'),
                   text(hbold('Balance Changes:\n'), account_inputs),
                   token_balances, f'Timestamp: {timestamp(block_time)}',
                   block, fee, sep='\n\n')
    return message


async def track_wallets():
    logging.info('Started tracking...')
    while True:
        try:
            client = AsyncClient(ENDPOINT)
            for wallet in db.get_all_wallets():
                tx_sig_json = await _latest_wallet_tx_sig(wallet[0], client)
                slot = _get_slot(tx_sig_json)
                if wallet[2] < slot:
                    tx_sig = _get_tx_sig(tx_sig_json)
                    tx_info = await get_tx_info(tx_sig, client)
                    db.update_slot(slot, wallet[0], wallet[1])
                    logging.info(f'Slot updated to {slot}')
                    notification = form_message(wallet, tx_info["result"], tx_sig)
                    await bot.send_message(wallet[1], notification)
                await asyncio.sleep(5)
            await client.close()
            await asyncio.sleep(5)
        except Exception as e:
            logging.exception(f'Exception', exc_info=e)
            await client.close()
            await asyncio.sleep(5)

async def run_bot():
    dp = Dispatcher(storage=storage)
    dp.include_router(form_router)
    logging.info('Start up')
    asyncio.create_task(track_wallets())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(run_bot())
