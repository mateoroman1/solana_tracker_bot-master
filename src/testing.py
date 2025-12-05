import asyncio
import logging
import sys
from dotenv import load_dotenv
from os import getenv
from typing import Any, Dict

from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from sqliter import SQLighter
from utils import get_balance_changes, to_sol, get_token_balances, timestamp

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, callback_data
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import text, hbold, hitalic, hlink, code
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

ENDPOINT = ""
ENDPOINT2 = ""
ENDPOINT_SOL = "https://api.mainnet-beta.solana.com"
TX_URL = 'https://solscan.io/tx/%s'
ADDRESS_URL = 'https://solscan.io/account/%s'
TOKEN_URL = 'https://www.pump.fun/%s'

db = SQLighter('wallets.db')

load_dotenv()

TOKEN = getenv('BOT_TOKEN')

jito_addr = ['11111111111111111111111111111111', 'ComputeBudget111111111111111111111111111111','96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5', 'HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe', 'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY', 'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49', 'DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh', 'ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt', 'DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL', '3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT']

wallet_ids=["TRANSIENT", "APES"]

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
form_router = Router()

class Menu(StatesGroup):
    menu = State()
    add_wallet = State()
    remove_wallet = State()
    see_wallets = State()

class callbacks(callback_data.CallbackData, prefix='w'):
    action: str

# ------------------------V CONVERTED TO 3.0
@form_router.message(CommandStart())
async def menu(message: Message, state: FSMContext):
    await state.set_state(Menu.menu)
    await message.answer(text= "Please select an action",
        reply_markup = InlineKeyboardMarkup(
        inline_keyboard = [
            [
                InlineKeyboardButton(text='Add wallet', callback_data = callbacks(action = 'add').pack()),
                InlineKeyboardButton(text='Remove wallet', callback_data = callbacks(action='remove').pack()),
                InlineKeyboardButton(text='See wallets', callback_data = callbacks(action='see').pack())
            ]
        ], 
    ))

# Now we just need reply commands for ADD/SEE/REMOVE

@form_router.callback_query(callbacks.filter(F.action == 'add'))
async def add(query: callback_data.CallbackQuery, state: FSMContext):
    await query.message.answer('Send wallet name and a 44 character sol wallet address, format: "name address"')
    await state.set_state(Menu.add_wallet)
    await query.answer()

@form_router.message(Menu.add_wallet)
async def process_add(message: Message, state: FSMContext):
    wallet = message.text.split()
    if len(wallet) != 2:
        await message.answer('Invalid syntax, should be "name address". Try again:')
        return
    result = await _latest_wallet_tx_sig(wallet[1])
    print(result)
    if result == 'error': # FIXME this should be checking for specific error within the response, but this is ok for now
        await message.answer('Invalid wallet address, try again:')
        return
    if db.wallet_exists(wallet[1], message.chat.id):
        await message.answer('Wallet already added, try again:')
        return
    slot = _get_slot(result)
    db.add_wallet(wallet[0], wallet[1], message.chat.id, slot)
    logging.info(f'Wallet added {wallet[0]} for {message.chat.id}')
    await message.answer('New wallet added!')
    await state.set_state(Menu.menu)

@form_router.callback_query(callbacks.filter(F.action == 'remove'))

@form_router.callback_query(callbacks.filter(F.action == 'see'))
async def see():
    pass

''' 

Solana RPC Utilities

'''
async def _latest_wallet_tx_sig(address: str, client: AsyncClient = None):
    if client:
        return await client.get_signatures_for_address(Pubkey.from_string(address), limit=1)
    async with AsyncClient(ENDPOINT) as client:
        return await client.get_signatures_for_address(Pubkey.from_string(address), limit=1)

def _get_tx_sig(response):
    return response.value[0].signature if response.value else None

def _get_slot(response):
    return response.value[0].slot if response.value else None

async def get_tx_info(tx_sig: str, client: AsyncClient = None):
    if client:
        return await client.get_transaction(tx_sig, encoding="jsonParsed", max_supported_transaction_version=0)
    async with AsyncClient(ENDPOINT) as client:
        return await client.get_transaction(tx_sig, encoding="jsonParsed", max_supported_transaction_version=0)
'''

Transaction Handling/Verifying

'''
def verify_funded(tx): 
    unneeded = jito_addr
    unneeded.extend(db.get_all_wallets())
    chatID = 6945939261
    accounts = [str(i.pubkey) for i in tx.message.account_keys if str(i.pubkey) not in unneeded]
    # - We get all accounts not utility
    # - if there's only two-three wallets we can ignore this because it's not a funding transaction probably should be at least 5
    if len(accounts) < 4 or ('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA' in accounts):
        logging.info(f'Non-funding TX')
        return False
    else:
        for i in accounts:
            if not db.wallet_exists(i, chatID):
                db.add_wallet('TRANSIENT', i, chatID, 0)
            else:
                continue
        
def form_transient_message(wallet, full_tx, tx_sig):
    logging.info(f'NOTIFICATION: Creating {tx_sig} on {wallet[3]}')
    block_time = full_tx.value.block_time
    meta = full_tx.value.transaction.meta
    status = 'Success' if not meta.err else meta.err
    parsed_tx = meta.inner_instructions[0].instructions[0].parsed['info']
    account_inputs = ''
    tx_type = 'Sell'
    if len(parsed_tx) == 2:
        token_addr = parsed_tx['mint']
        tx_type = 'Buy'
    else:
        token_addr = str(meta.pre_token_balances[0].mint)
    logging.info(f'{tx_type}: {token_addr}')
    message = text(f'Wallet tracked: {hlink(wallet[3], ADDRESS_URL % wallet[0])}', tx_type, f'Token CA: {hlink(token_addr, TOKEN_URL % token_addr)}\n {code(token_addr)}', hitalic(f'Status: {status}'),
                text(hbold('Balance Changes:\n'), account_inputs), f'Timestamp: {timestamp(block_time)}', sep='\n\n')
    return message
    

def form_message(wallet, full_tx, tx, tx_sig):
    logging.info(f'NOTIFICATION: Creating {tx.signatures} on {wallet[3]}')
    accounts_as_keys = [i.pubkey for i in tx.message.account_keys]
    accounts = [str(i) for i in accounts_as_keys]
    block_time = full_tx.value.block_time
    print('block time', block_time)
    meta = full_tx.value.transaction.meta
    status = 'Success' if not meta.err else meta.err
    fee = f"Transaction fee: {format(to_sol(meta.fee), '.6f')} sol"
    block = f"Block: {full_tx.value.slot}"
    balance_changes = get_balance_changes(accounts, meta.pre_balances, meta.post_balances)
    print('balance_changes', balance_changes)
    token_balance_changes = get_token_balances(accounts, meta.pre_token_balances,
                                               meta.post_token_balances)
    print('token_balance_changes', token_balance_changes)
    account_inputs = ''
    for account_input in balance_changes:
        address, post_balance, change = account_input
        change = '+' + str(change) if change > 0 else change
        if type(address) is list:
            account_inputs += f'{hlink(address[0], ADDRESS_URL % address[0])} | Balance: {post_balance} (change: {change}) sol\n'
        else:
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
    elif not meta.pre_token_balances and meta.post_token_balances:
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
            client2 = AsyncClient(ENDPOINT2)
            for wallet in db.get_all_wallets():
                tx_sig_json = await _latest_wallet_tx_sig(wallet[0], client2)
                slot = _get_slot(tx_sig_json)
                if slot == None or wallet[2] == None:
                    logging.info(f'Slot not recieved/read on {wallet}, Slot:{slot}')
                elif wallet[2] < slot:
                        tx_sig = _get_tx_sig(tx_sig_json)
                        tx_full = await get_tx_info(tx_sig, client)
                        tx_info = tx_full.value.transaction.transaction
                        if str(tx_info.message.account_keys[0].pubkey) in ['FLiPggWYQyKVTULFWMQjAk26JfK5XRCajfyTmD5weaZ7', 'Habp5bncMSsBC3vkChyebepym5dcTNRYeg2LVG464E96']:
                            logging.warning(f' Flip.gg/Lootbox Spam')
                            db.update_slot(slot, wallet[0], wallet[1])
                        else:
                            db.update_slot(slot, wallet[0], wallet[1])
                            if wallet[3] in wallet_ids and len(tx_full.value.transaction.meta.inner_instructions) > 0:
                                logging.info(f'TOKEN PURCHASE {wallet[0]}')
                                notification = form_transient_message(wallet, tx_full, tx_sig)
                                await bot.send_message(wallet[1], notification)
                            elif wallet[3] not in wallet_ids:
                                verify_funded(tx_info)
                                logging.info(f'Slot updated to {slot}')
                                notification = form_message(wallet, tx_full, tx_info, tx_sig)
                                await bot.send_message(wallet[1], notification)
                await asyncio.sleep(1)
            await client.close()
            await asyncio.sleep(1)
        except Exception as e:
            logging.exception(f'Exception', exc_info=e)
            await client.close()
            await asyncio.sleep(5)
'''

Run Bot

'''
async def main():
    dp = Dispatcher()
    dp.include_router(form_router)
    asyncio.create_task(track_wallets())
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

# in GCP tmux attach -t mysession
