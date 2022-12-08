# PyNiceCalc

This project started off as a basic nicehash profitability calculator and has since evolved in to more of a Nicehash marketplace mining management script. The features are pretty sporatically complete as I only really develop features as I need them. I've done my best to ensure that it works as expected with all of the coins defined by default in `algo_query_map.json` but I've only really extensively tested sha256 and scrypt. I've confirmed that the others work at a glance but there may be bugs so just watch out for that...

Speaking of the `algo_query_map.json` file. I've started to work out how to make this map a little more generic. Originally, all profitability data was sourced from whattomine.com and was only inclusive of the asic algorithms which were supported by Nicehash. As the project has evolved, I started to incorporate the algorithms listed on the WTM GPU page as well. This necessitated a rewrite of the original query lookup map and I took the opportunity to make it a little more flexible in the hopes that it's easy to extend beyond just WTM for profitability data. If you want to add an algorithm to the query map, the basic object structure is shown below:

```json
{ 
    "algorithm_name": {
        "url": "https://some_url_that_returns_json",
        "key": "top_level_json_key_for_data"
    }
}
```
As you may have guessed, there is a glaring issue here and I've yet to figure out how to work around it. Namely, in working primarily with WTM data, all of the relevant profitability data is nested inside of a top-level object (for WTM it's "coins"). The code is written in such a way that it assumes your data source is formatted the same. Obviously, I'll need to figure out a way to handle more arbitrarily formatted json in the future, but for now, this works.

Currently, the script expects that you create a config.ini (by default in $CWD but can be defined with `--config` at runtime). The example config shows a rough outline of how this config should look. In short, section `[DEFAULT]` is the main stuff and is all required. Each subsequent section is an order number ['xxx-xxx-xxx-xxx'] (where xxx-xxx-xxx-xxx is the order ID) with a single boolean parameter `manage`. For now, if you want the script to dynamically adjust and manage an order based on market conditions, you need to create a block for the order and set `manage` to `True`. If you don't do this, even if you use the `--manage` flag at runtime, the script will ignore your orders and just give you profitability information. In the future, I hope to avoid the need for setting `manage = True` in the config and only require `manage = False` if there's an order you explicitely want to ignore when you enable order management at runtime. That will probably come when I add the bits to enable order creation and deletion as the APIs are kinda grouped there.

If you have one or more active orders defined in the `config.ini` and you have set `manage=True` for one or more of the order IDs, then the bot will fetch that order's information and compare it against the theoretical profitability for the algorithm as calculated by whattomine.com. By default, we pull the profitability data ordered by 24h profitability and pick the most profitable one as our expected profit. If this information is not what you want, there is a `-c` flag. You can provide the `--coin` argument, which is a string representing a coin that mines with the target algorithm, one or more times at run time. If more than one coin is specified, the profitabilities will be added together and used as the target profitability reference. This is useful when mining a single algorithm on a pool that supports dual or merge mining. For example `python calculate.py -a scrypt` will show you profitability based on expected returns from Nicehash. If for some reason you don't want to use this, you can specific the coin symbol as the value to a `-c` argument, for example: `python calculate.py -a scrypt -c doge` will specifically pull dogecoin profitability. Providing `-c` twice will add the two coin's profitability together, for example: `python calculate.py -a scrypt -c doge -c ltc`.

One thing to keep in mind, I don't usually have more than one order open at a time. Theoretically, this script should be able to manage more than one open order for the same algorithm but I've never tested it. Use this script to manage your orders at your own risk, especially if you're trying to manage anything that's not a single Scrypt mining order. If in doubt and you still want to manage multiple orders, create multiple config files, one per order, containing a block for just one order and run multiple instances of the script targeting the appropriate algorithm (and, optionally, coin) with the corresponding config with `--config`.

# Setup
The project was written with python 3.10.5 in mind, other minor versions of python3 will probably still work but if you hit an issue and you're not on the version defined in `.python-version`, I can't make any promises I'll fix it. To ensure that you don't have issues, install and use pyenv to automatically use the version defined in `.python-version` any time you're in the project directory.

```
$ git clone git@github.com:tedwardd/pynicecalc.git
$ cd pynicecalc
$ pip install -r requirements.txt
```

# Config Example

```
[DEFAULT]
host = https://api2.nicehash.com
organization_id = # Get this from nicehash profile
key = # Nicehash API key
secret = # Nicehash API secret

[xxxx-xxxx-xxxx-xxxx]
manage=True
```