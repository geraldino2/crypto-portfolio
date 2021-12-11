import ccxt
import yaml
import requests

from web3.middleware import geth_poa_middleware
from web3 import Web3

with open("config.yaml") as config_file:
	CFG = yaml.safe_load(config_file)
	WALLET_ADDRESS = checksum_address(w3, CFG["wallet_address"])

chains = {
	"bsc": {
		"explorer_api_key": CFG["bscscan_api_key"],
		"explorer_api_url":  CFG["bscscan_api_url"],
		"dex_router_address": CFG["pancake_router"],
		"wrapped_token_address": CFG["bsc_wbnb"],
		"usdt_address": CFG["bsc_usdt"]
	},
	"avalanche-c": {
		"explorer_api_key": CFG["snowtrace_api_key"],
		"explorer_api_url":  CFG["snowtrace_api_url"],
		"dex_router_address": CFG["traderjoe_router"],
		"wrapped_token_address": CFG["avax_wavax"],
		"usdt_address": CFG["avax_usdt"]
	}
}

def w3_instance(
		address:str
		) -> Web3:
	w3 = Web3(Web3.HTTPProvider(address))
	w3.middleware_onion.inject(geth_poa_middleware, layer=0)
	return w3

def checksum_address(
		w3:Web3,
		address:str
		):
	return w3.toChecksumAddress(address.lower())

def normalize_balance(
		w3:Web3,
		price
		) -> float:
	return float(w3.fromWei(price, "ether"))

def get_abi(
		chain:dict,	
		contract_address:str
		) -> dict:
	api_key = chain["explorer_api_key"]
	api_url = chain["explorer_api_url"]
	params = dict()
	params["module"] = "contract"
	params["action"] = "getabi"
	params["address"] = contract_address
	params["apikey"] = api_key
	req = requests.get(api_url, params=params)
	return req.json()["result"]

def wcoin_usdt_price(
		w3:Web3, 
		chain:dict
		) -> float:
	api_key = chain["explorer_api_key"]
	api_url = chain["explorer_api_url"] 
	router = checksum_address(w3, chain["dex_router_address"])
	wcoin = checksum_address(w3, chain["wrapped_token_address"])
	usdt = checksum_address(w3, chain["usdt_address"])
	abi = get_abi(api_key, api_url, router)
	router = w3.eth.contract(address=router, abi=abi)
	wcoin_usd = router.functions.getAmountsOut(w3.toWei("1", "ether"), [wcoin, usdt]).call()
	return float(normalize_balance(w3,wcoin_usd[1]))

def dex_price(
		w3:Web3, 
		chain:dict,
		wcoin_usdt_price:float, 
		contract_address:str
		) -> list:
	api_key = chain["explorer_api_key"]
	api_url = chain["explorer_api_url"] 
	router = checksum_address(w3, chain["dex_router_address"])
	wcoin_address = checksum_address(w3, chain["wrapped_token_address"])
	usdt_address = checksum_address(w3, chain["usdt_address"])
	contract_address = checksum_address(w3, contract_address)
	token_abi = get_abi(api_key, api_url, contract_address)
	router_abi = get_abi(api_key, api_url, router)

	router = w3.eth.contract(address=router, abi=router_abi)

	token_contract = w3.eth.contract(address=contract_address, abi=token_abi)
	decimals = token_contract.functions.decimals().call()

	try:
		txn = router.functions.getAmountsOut(10**decimals, 
											[contract_address, wcoin_address]
											).call()
		coin_token = normalize_balance(w3,txn[1])
		usd_token = coin_token*wcoin_usdt_price
	except: #wcoin pair not found, usdt pair may exist
		try:
			txn = router.functions.getAmountsOut(10**decimals,
												[contract_address, usdt_address]
												).call()
			usd_token = normalize_balance(w3,txn[1])
			coin_token = usd_token/wcoin_usdt_price
		except: #neither usdt nor wrapped token pairs exist
			return [None, None]
	return [coin_token, usd_token]

subtotal = 0

print("BSC")
print("-"*40)
w3 = w3_instance(CFG["bsc_address"])
BNB_USDT_PRICE = wcoin_usdt_price(w3, chains["bsc"])
balance = normalize_balance(w3, w3.eth.get_balance(WALLET_ADDRESS))
usd_balance = balance*BNB_USDT_PRICE
subtotal += float(usd_balance)
print(f"BNB (${round(BNB_USDT_PRICE,8)})")
print(f"{round(balance,8)} = ${round(usd_balance,3)}")
bep20_contracts_addr = set()
with open("bep20_contracts") as bep20_contracts_file:
	for contract_address in bep20_contracts_file.read().split("\n"):
		bep20_contracts_addr.add(contract_address)
for contract_address in bep20_contracts_addr:
	abi = get_abi(chains["bsc"], contract_address)
	contract = w3.eth.contract(address=checksum_address(w3,contract_address),
								abi=abi)
	balance = contract.functions.balanceOf(WALLET_ADDRESS).call()
	symbol = contract.functions.symbol().call().upper()
	balance = normalize_balance(w3,balance)
	if(balance>0):
		usd_price = dex_price(w3,
								chains["bsc"],
								BNB_USDT_PRICE, 
								contract_address)[1]
		if(usd_price == None):
			continue
		usd_balance = usd_price*balance
		subtotal += float(usd_balance)
		print(f"{symbol} (${round(usd_price,8)})")
		print(f"{round(balance,8)} = ${round(usd_balance,3)}")
print("-"*40)

print("AVAX C-CHAIN")
print("-"*40)
w3 = w3_instance(CFG["avax_address"])
AVAX_USDT_PRICE = wcoin_usdt_price(w3, 
								chains["avalanche-c"])*10**12
balance = normalize_balance(w3,
							w3.eth.get_balance(WALLET_ADDRESS))
usd_balance = balance*AVAX_USDT_PRICE
subtotal += float(usd_balance)
print(f"AVAX (${round(AVAX_USDT_PRICE,8)})")
print(f"{round(balance,8)} = ${round(usd_balance,3)}")
avaxc_contracts_addr = set()
with open("avaxc_contracts") as avaxc_contracts_file:
	for contract_address in avaxc_contracts_file.read().split("\n"):
		avaxc_contracts_addr.add(contract_address)
for contract_address in avaxc_contracts_addr:
	abi = get_abi(chains["avalanche-c"], contract_address)
	contract = w3.eth.contract(address = checksum_address(w3,contract_address),
								abi = abi)
	balance = contract.functions.balanceOf(WALLET_ADDRESS).call()
	symbol = contract.functions.symbol().call().upper()
	balance = normalize_balance(w3,balance)
	if(balance>0):
		usd_price = dex_price(w3,
								chains["avalanche-c"],
								AVAX_USDT_PRICE, 
								contract_address)[1]
		if(usd_price == None):
			continue
		usd_balance = usd_price*balance
		subtotal += float(usd_balance)
		print(f"{symbol} (${round(usd_price,8)})")
		print(f"{round(balance,8)} = ${round(usd_balance,3)}")
print("-"*40)

print("Binance")
print("-"*40)
exchange_id = "binance"
exchange_class = getattr(ccxt, exchange_id)
binance = exchange_class({
	"apiKey": CFG["binance_api_key"],
	"secret": CFG["binance_secret_key"],
})
balances = binance.fetchBalance()
for key in balances["total"]:
	if(key == "NFT"):
		continue
	if(balances["total"][key]>0):
		price = float(binance.fetchTicker(f"{key}/USDT")["info"]["lastPrice"])
		balance = balances['total'][key]
		print(f"{key} (${round(price,8)})")
		print(f"{round(balance,8)} = ${round(balance*price,3)}")
		subtotal += float(balance*price)
print("-"*40)
print(f"Subtotal: ${subtotal}\n")
