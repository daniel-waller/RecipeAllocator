import json
import numpy as np
import pandas as pd
import logging
logging.basicConfig(filename='recipeallocator.log',level=logging.DEBUG)
logger = logging.getLogger(__name__)

def obtain_numbers(string):

    #---------
    # FUNCTION to take a string eg. "three_portions","two_recipes", and return the associated number.
    # If string is incorrectly formatted, returns the string.
    # --------
    # Inputs:
    #   - string: A string of form "num_XXXX..."
    # Outputs:
    #   - The corresponding number.
    # --------

    # Dictionary of numbers (can be expanded if more possibilities desired)
    numberdict =  {"two": 2, "three": 3, "four": 4}

    # Identifies the number
    if isinstance(string, str):
        num = string.split("_")[0]
        if num in numberdict.keys():
            return numberdict[num]
        else:
            return string
    else:
        return string



def allocate_recipes(N_orders,stock_levels,N_portions,N_recipes):

    # ---------
    # FUNCTION to allocate recipes to customers
    # Returns the remaining stock levels and the number of orders left over (0 if successful)
    # --------
    # Inputs:
    #   - N_orders: the number of customers in the category
    #   - stock_levels: quantities of each recipe left in stock
    #   - N_portions: the number of portions for these customers
    #   - N_recipes: the number of recipes_per_box for these customers
    # Outputs:
    #   - The remaining stock levels
    #   - The number of orders that can't be fulfilled.
    # --------

    # Are there enough recipes left in stock to meet N_recipes?
    if len(stock_levels) < N_recipes:
        logger.info("{} recipes-per-box but only {} recipes in stock".format(N_recipes,len(stock_levels)) )
        return stock_levels, N_orders

    for N_orders_left in range(N_orders, 0, -1):
        # Finding the recipes with highest available stock
        recipe_choices = np.argpartition(stock_levels,-N_recipes)[-N_recipes:]

        # Checking stock is high enough. If not, the function breaks out.
        if stock_levels[recipe_choices].min() < N_portions:
            return stock_levels, N_orders_left

        # Subtracting the choices from stock levels.
        stock_levels[recipe_choices] = stock_levels[recipe_choices] - N_portions

    return stock_levels, 0

def fulfil_orders(StockDF, OrdersDF, Ordersdict):

    # ---------
    # FUNCTION to fulfil orders
    # Takes arrays for
    # --------
    # Inputs:
    #   - StockDF - the levels of stock for each recipe, with meal type.
    #   - OrdersDF - a numpy array containing orders by category.
    #   - Ordersdict - a dictionary containing labels for each dimension of OrdersDF
    # Outputs:
    #   - Either True (if all orders are fulfilled) or False (if they aren't)
    # --------

    stocks = StockDF["stock_count"].values.copy()
    # Splitting stocks by meal type
    veg_stocks = (StockDF["box_type"] == "vegetarian").values
    gourmet_stocks = (StockDF["box_type"] == "gourmet").values

    # We call allocate_recipes() for different subsets of customers, ordering according to the following priorities:
    #   1. Number of portions per recipe (greatest to smallest)
    #   2. Vegetarian, then gourmet
    #   3. Number of recipes per box (greatest to smallest)

    logger.info("Allocating recipes:")
    for j in range(0,OrdersDF.shape[1]):
        for i in range(0,OrdersDF.shape[0]):
            for k in range(0,OrdersDF.shape[2]):

                logger.info("{},{} portions, {} recipes-per-box".format(Ordersdict[0][i],Ordersdict[1][j],Ordersdict[2][k]))
                # Vegetarian orders are passed "veg_stocks".
                if Ordersdict[0][i] == "vegetarian":
                    stocks_left, orders_left = allocate_recipes(OrdersDF[i,j,k],stocks[veg_stocks],Ordersdict[2][k], Ordersdict[1][j])

                    # If we're unsuccessful, return False, otherwise move on.
                    if orders_left > 0:
                        logger.info("Unable to fulfil, {} order(s) left".format(orders_left))
                        return False
                    else: stocks[veg_stocks] = stocks_left

                # Gourmet orders are passed "gourmet_stocks" first.
                elif Ordersdict[0][i] == "gourmet":
                    stocks_left, orders_left = allocate_recipes(OrdersDF[i, j, k], stocks[gourmet_stocks], Ordersdict[2][k],Ordersdict[1][j])

                    # If we're unsuccessful, we try expanding to include all recipes including vegetarian
                    if orders_left > 0:
                        logger.info("{} orders left, including vegetarian recipes".format(orders_left))
                        stocks_left, orders_left = allocate_recipes(orders_left, stocks, Ordersdict[2][k],Ordersdict[1][j])

                        # If we're still unsuccessful, now False is returned. If successful, we move on.
                        if orders_left > 0:
                            logger.info("Unable to fulfil, {} order(s) left".format(orders_left))
                            return False
                        else: stocks = stocks_left

                    else: stocks[gourmet_stocks] = stocks_left

    # Reaching the end of the loop means all orders successfully processed.
    logger.info("All orders processed")
    return True

def load_files(order_file,stock_file):

    # ---------
    # FUNCTION to load/clean files
    # Takes JSON input files and turns them into the inputs for fulfil_orders.
    # --------
    # Inputs:
    #   - order_file - the filepath to the JSON file containing the orders.
    #   - stock_file - the filepath to the JSON file containing the stocks.
    # Outputs:
    #   - StockDF - Dataframe containing the stock counts and meal type for each recipe
    #   - OrdersDF - Numpy array containing the order numbers by meal type, portion count, and recipe count.
    # --------

    # Loading files
    f = open(order_file,)
    orders = json.load(f)
    f.close()
    logging.debug('Loaded {}'.format(order_file))

    g = open(stock_file, )
    stock = json.load(g)
    g.close()
    logging.debug('Loaded {}'.format(stock_file))

    # Stock dataframe is ready to go
    StockDF = pd.DataFrame.from_dict(stock).T

    # Orders dataframes need string conversion and sorting by portion, recipe counts.
    VegOrdersDF = pd.DataFrame.from_dict(orders.get('vegetarian'))
    GourmOrdersDF = pd.DataFrame.from_dict(orders.get('gourmet'))

    # Converting the strings for portion, recipe counts to numbers, and relabelling the dataframes
    colnames = []
    for i in VegOrdersDF.columns:
        colnames.append(obtain_numbers(i))
    VegOrdersDF.columns = colnames
    GourmOrdersDF.columns = colnames

    indexnames = []
    for i in VegOrdersDF.index:
        indexnames.append(obtain_numbers(i))
    VegOrdersDF.index = indexnames
    GourmOrdersDF.index = indexnames

    # Sorting the orders by portion count and by
    VegOrdersDF.sort_index(axis=0, ascending=False, inplace=True)
    VegOrdersDF.sort_index(axis=1, ascending=False, inplace=True)
    GourmOrdersDF.sort_index(axis=0, ascending=False, inplace=True)
    GourmOrdersDF.sort_index(axis=1, ascending=False, inplace=True)

    # Recombining the orders into a numpy array
    OrdersDF = np.array([np.array(VegOrdersDF),np.array(GourmOrdersDF)])

    # Creating the dictionary with category information
    Ordersdict = {0: ["vegetarian","gourmet"], 1: VegOrdersDF.index , 2: VegOrdersDF.columns}

    return StockDF, OrdersDF, Ordersdict

def default_orders_satisfied(order_file,stock_file):

    # ---------
    # FUNCTION Overall wrapper to just take file names and return the outcome.
    # --------
    # Inputs:
    #   - order_file - the filepath to the JSON file containing the orders.
    #   - stock_file - the filepath to the JSON file containing the stocks.
    # Outputs:
    #   - Either True (if all orders are fulfilled) or False (if they aren't)
    # --------

    StockDF, OrdersDF, Ordersdict = load_files(order_file,stock_file)
    return fulfil_orders(StockDF, OrdersDF, Ordersdict)
