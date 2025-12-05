import asyncio
from solana.rpc.async_api import AsyncClient
from solders.signature import Signature

ENDPOINT = "https://api.mainnet-beta.solana.com"
TX_URL = 'https://explorer.solana.com/tx/%s'
ADDRESS_URL = 'https://explorer.solana.com/address/%s'


async def get_tx_info(tx_sig: str, client: AsyncClient = None):
    if client:
        return await client.get_transaction(tx_sig, encoding='jsonParsed', max_supported_transaction_version=0)
    async with AsyncClient(ENDPOINT) as client:
        return await client.get_transaction(tx_sig, encoding ='jsonParsed', max_supported_transaction_version=0)

txsig = Signature.from_string('XxGn5tEXszt966nX5BSEij89NMHBNAJgDdoAWwhHUx2KeeFVcHEZkUaQZeYriGDKThGyQwS8dd67RzvN9RR7C3S')
#txsig = Signature.from_string('bM8BXTjbHSAvyTvoXuiGnjnnm8YAFZmmRYjjeQpyMfzm6hvupMVznj59UkorUiEJjTohVi3TnMPuFCVadp3XcQp')
txsig2 = Signature.from_string('4G6dvozcnMcjhydkrjhJ9TxEgnCHLjizEZzojWPiAkLS35SWmJ9ZUswg7HBbBWbMh7gzLMDwTgFQJ6rCPMUTshAF')

client = AsyncClient(ENDPOINT)

async def main():
    tx = await get_tx_info(txsig, client)
    #await asyncio.sleep(2)
    #tx2 = await get_tx_info(txsig2, client)
    print(tx.value.transaction.transaction.signatures[0])
    #print(len(tx.value.transaction.meta.inner_instructions))
    #print(tx2.value.transaction.transaction.message.account_keys[0].pubkey)
    #acctlist = [i.pubkey for i in tx2.value.transaction.transaction.message.account_keys]
    #print(acctlist[0])
    #print(tx.value.transaction.meta.pre_token_balances[0])
    
asyncio.run(main())