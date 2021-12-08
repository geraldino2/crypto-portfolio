import ccxt
import yaml
import requests

from web3.middleware import geth_poa_middleware
from web3 import Web3

with open("config.yaml") as config_file:
	CFG=yaml.safe_load(config_file)

def w3_instance(address:str):
	w3 = Web3(Web3.HTTPProvider(address))
	w3.middleware_onion.inject(geth_poa_middleware, layer=0)
	return w3

def checksum_address(w3:Web3, address:str):
	return w3.toChecksumAddress(address.lower())

def normalize_balance(w3:Web3, price):
	return float(w3.fromWei(price, "ether"))

def get_abi(api_key:str, api_url:str, contract_address:str) -> dict:
	params = dict()
	params["module"] = "contract"
	params["action"] = "getabi"
	params["address"] = contract_address
	params["apikey"] = api_key
	req = requests.get(api_url, params=params)
	return req.json()["result"]

def wcoin_usdt_price(w3:Web3, api_key:str, api_url:str, router, wcoin, usdt) -> float:
	abi = get_abi(api_key, api_url, router)
	router = w3.eth.contract(address=router, abi=abi)
	wcoin_usd = router.functions.getAmountsOut(w3.toWei("1", "ether"), [wcoin, usdt]).call()
	return(float(normalize_balance(w3,wcoin_usd[1])))

def dex_price(w3:Web3, api_key:str, api_url:str, router, WCOIN_ADDRESS, USDT_ADDRESS, WCOIN_USDT_PRICE, contract_address:str) -> list:
	contract_address = checksum_address(w3,contract_address)
	token_abi = get_abi(api_key, api_url, contract_address)
	router_abi = get_abi(api_key, api_url, router)

	router = w3.eth.contract(address=router, abi=router_abi)

	token_contract = w3.eth.contract(address=checksum_address(w3, contract_address), abi=token_abi)
	decimals = token_contract.functions.decimals().call()

	try:
		txn = router.functions.getAmountsOut(10**decimals, [contract_address, WCOIN_ADDRESS]).call()
		coin_token = normalize_balance(w3,txn[1])
		usd_token = coin_token*WCOIN_USDT_PRICE
	except: #wcoin pair not found, usdt pair may exist
		try:
			txn = router.functions.getAmountsOut(10**decimals, [contract_address, BSC_USDT_ADDRESS]).call()
			usd_token = normalize_balance(w3,txn[1])
			coin_token = usd_token/WCOIN_USDT_PRICE
		except: #neither usdt nor bnb pairs exist
			return [None, None]
	return [coin_token, usd_token]

subtotal=0

print("-"*40)
print("BSC")
print("-"*40)
w3 = w3_instance(CFG["bsc_address"])
BSCSCAN_API_KEY=CFG["bscscan_api_key"]
BSCSCAN_API_URL=CFG["bscscan_api_url"]
PANCAKE_ROUTER=CFG["pancake_router"]
BSC_WBNB_ADDRESS=CFG["bsc_wbnb"]
BSC_USDT_ADDRESS=CFG["bsc_usdt"]
BNB_USDT_PRICE=wcoin_usdt_price(w3, 
								BSCSCAN_API_KEY, 
								BSCSCAN_API_URL, 
								PANCAKE_ROUTER, 
								BSC_WBNB_ADDRESS, 
								BSC_USDT_ADDRESS)
balance = normalize_balance(w3,
							w3.eth.get_balance(CFG["wallet_address"]))
usd_balance = balance*BNB_USDT_PRICE
subtotal += float(usd_balance)
print(f"BNB (${round(BNB_USDT_PRICE,8)})")
print(f"{round(balance,8)} = ${round(usd_balance,3)}")
bep20_contracts_addr=set()
with open("bep20_contracts") as bep20_contracts_file:
	for contract_address in bep20_contracts_file.read().split("\n"):
		bep20_contracts_addr.add(contract_address)
for contract_address in bep20_contracts_addr:
	abi = get_abi(BSCSCAN_API_KEY, BSCSCAN_API_URL, contract_address)
	contract = w3.eth.contract(address=checksum_address(w3,contract_address),
								abi=abi)
	balance = contract.functions.balanceOf(checksum_address(w3,CFG["wallet_address"])).call()
	symbol = contract.functions.symbol().call().upper()
	balance = normalize_balance(w3,balance)
	if(balance>0):
		usd_price = dex_price(w3,
								BSCSCAN_API_KEY,
								BSCSCAN_API_URL,
								PANCAKE_ROUTER,
								BSC_WBNB_ADDRESS,
								BSC_USDT_ADDRESS,
								BNB_USDT_PRICE, 
								contract_address)[1]
		usd_balance = usd_price*balance
		subtotal += float(usd_balance)
		print(f"{symbol} (${round(usd_price,8)})")
		print(f"{round(balance,8)} = ${round(usd_balance,3)}")
print("-"*40)

print("AVAX C-CHAIN")
print("-"*40)
w3 = w3_instance(CFG["avax_address"])
SNOWTRACE_API_KEY=CFG["snowtrace_api_key"]
SNOWTRACE_API_URL=CFG["snowtrace_api_url"]
JOE_ROUTER=checksum_address(w3,CFG["traderjoe_router"])
AVAX_WAVAX_ADDRESS=checksum_address(w3,CFG["avax_wavax"])
AVAX_USDT_ADDRESS=checksum_address(w3,CFG["avax_usdt"])
AVAX_USDT_PRICE=wcoin_usdt_price(w3, 
								SNOWTRACE_API_KEY, 
								SNOWTRACE_API_URL, 
								JOE_ROUTER, 
								AVAX_WAVAX_ADDRESS, 
								AVAX_USDT_ADDRESS)*10**12
balance = normalize_balance(w3,
							w3.eth.get_balance(CFG["wallet_address"]))
usd_balance = balance*AVAX_USDT_PRICE
subtotal += float(usd_balance)
print(f"AVAX (${round(AVAX_USDT_PRICE,8)})")
print(f"{round(balance,8)} = ${round(usd_balance,3)}")
avaxc_contracts_addr=set()
with open("avaxc_contracts") as avaxc_contracts_file:
	for contract_address in avaxc_contracts_file.read().split("\n"):
		avaxc_contracts_addr.add(contract_address)
for contract_address in avaxc_contracts_addr:
	abi = get_abi(SNOWTRACE_API_KEY, SNOWTRACE_API_URL, contract_address)
	contract = w3.eth.contract(address=checksum_address(w3,contract_address),
								abi=abi)
	balance = contract.functions.balanceOf(checksum_address(w3,CFG["wallet_address"])).call()
	symbol = contract.functions.symbol().call().upper()
	balance = normalize_balance(w3,balance)
	if(balance>0):
		usd_price = dex_price(w3,
								SNOWTRACE_API_KEY,
								SNOWTRACE_API_URL,
								JOE_ROUTER,
								AVAX_WAVAX_ADDRESS,
								AVAX_USDT_ADDRESS,
								AVAX_USDT_PRICE, 
								contract_address)[1]
		usd_balance = usd_price*balance
		subtotal += float(usd_balance)
		print(f"{symbol} (${round(usd_price,8)})")
		print(f"{round(balance,8)} = ${round(usd_balance,3)}")
print("-"*40)

print("Binance")
print("-"*40)
exchange_id="binance"
exchange_class=getattr(ccxt, exchange_id)
binance=exchange_class({
	"apiKey": CFG["binance_api_key"],
	"secret": CFG["binance_secret_key"],
})
balances=binance.fetchBalance()
for key in balances["total"]:
	if(key=="NFT"):
		continue
	if(balances["total"][key]>0):
		price=float(binance.fetchTicker(f"{key}/USDT")["info"]["lastPrice"])
		balance=balances['total'][key]
		print(f"{key} (${round(price,8)})")
		print(f"{round(balance,8)} = ${round(balance*price,3)}")
		subtotal += float(balance*price)
print("-"*40)
print(f"Subtotal: ${subtotal}\n")
