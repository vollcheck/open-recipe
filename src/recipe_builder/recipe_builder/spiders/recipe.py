# -*- coding: utf-8 -*-
import re
import scrapy
import csv
import json
from src.recipe import Recipe, Nutrition


def get_urls_from_data(data_path: str, sample):
    """
    Finds and returns a list of URLs from the recipes.csv dataset.
    :param data_path: path to the input csv list
    :param sample: if given, the function will return only n=sample urls
    :return: list of urls
    """
    bbc_urls = []
    all_recipes_urls = []
    with open(data_path) as csv_file:
        csv_reader = csv.reader(csv_file)
        for index, row in enumerate(csv_reader):
            if sample > 0:
                if bbc_urls.__len__() < sample and "www.bbcgoodfood.com" in row[0]:
                    bbc_urls.append(row[0])
            elif "www.bbcgoodfood.com" in row[0]:
                bbc_urls.append(row[0])

    return {
        "bbc": bbc_urls,
        "all_recipes": all_recipes_urls
    }


class GoodFoodSpider(scrapy.Spider):
    name = 'goodfood'
    cleanr = re.compile('<.*?>')

    def __init__(self, sample=0, **kwargs):
        super().__init__(**kwargs)
        self.start_urls = get_urls_from_data(
            "../data/input/recipes.csv", sample)['bbc']

    def parse(self, response):
        # NOTE Looks like the webpage layout changed since this was last written. Providing new parsing
        # rules to accomodate the new layout. Luckily, it looks like the recipe page has its data
        # represented in a JSON object towards the bottom.
        recipe_json = json.loads(response.xpath(
            '//script[contains(@id, "__NEXT_DATA__")]/text()').get())
        props = recipe_json['props']
        pageProps = props['pageProps']
        # The actual content
        description = re.sub(self.cleanr, '',
                             pageProps.get('description')[0].get('data').get('value'))  # getting 1st desc
        title = pageProps['title']
        author = (pageProps.get('authors')[0].get('suffix')[1:-1]
                  if pageProps.get('authors')[0].get('suffix') == '(GoodFood Community)'
                  else pageProps.get('authors')[0].get('name'))  # Just getting the first author
        ingredients_list = list(map(lambda ingredient_obj: ingredient_obj['ingredients'],
                                    pageProps['ingredients']))
        ingredients = []
        for i in range(len(ingredients_list)):
            for j in range(len(ingredients_list[i])):
                ingredients.append(
                    (ingredients_list[i][j].get('quantityText') + ' '
                     if 'quantityText' in ingredients_list[i][j].keys()
                     else '') + ingredients_list[i][j].get('ingredientText')
                )
        # Don't know why there's ingredients in ingredients

        nutritional_info_dict = {
            info_block['label']: info_block for info_block in pageProps.get('nutritionalInfo')
        }

        kcal = str(nutritional_info_dict.get('kcal').get('value')) if 'kcal' in nutritional_info_dict.keys() else None
        fat = (str(nutritional_info_dict.get('fat').get('value')) + ' ' +
               nutritional_info_dict.get('fat').get('suffix')) if 'fat' in nutritional_info_dict.keys() else None
        saturates = (str(nutritional_info_dict.get('saturates').get('value')) + ' ' +
                     nutritional_info_dict.get('saturates').get('suffix')) if 'saturates' in nutritional_info_dict.keys() else None
        carbs = (str(nutritional_info_dict.get('carbs').get('value')) + ' ' +
                 nutritional_info_dict.get('carbs').get('suffix')) if 'carbs' in nutritional_info_dict.keys() else None
        sugar = (str(nutritional_info_dict.get('sugars').get('value')) + ' ' +
                 nutritional_info_dict.get('sugars').get('suffix')) if 'sugars' in nutritional_info_dict.keys() else None
        fibre = (str(nutritional_info_dict.get('fibre').get('value')) + ' ' +
                 nutritional_info_dict.get('fibre').get('suffix')) if 'fibre' in nutritional_info_dict.keys() else None
        protein = (str(nutritional_info_dict.get('protein').get('value')) + ' ' +
                   nutritional_info_dict.get('protein').get('suffix')) if 'protein' in nutritional_info_dict.keys() else None
        salt = (str(nutritional_info_dict.get('salt').get('value')) + ' ' +
                nutritional_info_dict.get('salt').get('suffix')) if 'salt' in nutritional_info_dict.keys() else None

        skill_level = pageProps['skillLevel']

        time = None
        if pageProps.get('cookAndPrepTime').get('cookingMax') != 0:
            timePrep = float(pageProps.get(
                'cookAndPrepTime').get('preparationMax'))
            timeCook = float(pageProps.get(
                'cookAndPrepTime').get('cookingMax'))
            time = {
                'prep': {
                    # time is in seconds in the JSON data
                    'hrs': int(timePrep // 3600),
                    'mins': int((timePrep - ((timePrep // 3600) * 3600)) // 60)
                },
                'cook': {
                    'hrs': int(timeCook // 3600),
                    'mins': int((timeCook - ((timeCook // 3600) * 3600)) // 60)
                }
            }
        else:
            timeTotal = float(pageProps.get('cookAndPrepTime').get('total'))
            time = {
                'prep': {
                    'hrs': 0,  # time is in seconds
                    'mins': 0
                },
                'cook': {
                    'hrs': int(timeTotal // 3600),
                    'mins': int((timeTotal - ((timeTotal // 3600) * 3600)) // 60)
                }
            }
        method_steps_content = list(
            map(lambda step_content: step_content['content'], pageProps['methodSteps']))
        method_steps_list = list(
            map(lambda content_data: list(
                map(lambda content: content.get('data').get('value'), content_data)), method_steps_content))
        # removing any HTML in the recipe steps and flattening list
        method_steps = []
        for i in range(len(method_steps_list)):
            for j in range(len(method_steps_list[i])):
                method_steps.append(re.sub(
                    self.cleanr, '', method_steps_list[i][j]))

        servings = int(list(
            filter(lambda servings_part: servings_part.isnumeric(),
                   pageProps['servings'].split())
        )[0]) or None  # Grabbing the 1st number
        img = pageProps.get('seoMetadata').get('image').get('url') if 'image' in pageProps.get('seoMetadata').keys() else None

        nutrition_object = Nutrition(
            kcal, fat, saturates, carbs, sugar, fibre, protein, salt)

        recipe_object = Recipe(title, author, description, nutrition_object, ingredients,
                               method_steps, time, skill_level, servings, img)
        # Information from header includes title, author, cook time, difficulty, servings
        # and nutritional information
        # header = response.xpath('//div[contains(@class, "recipe-header")]')
        # recipe_title = header.xpath('h1[contains(@class, "recipe-header__title")]/text()')
        # attrib = header.xpath('//div[contains(@class, "recipe-header__chef")]/span/a/text()')
        # img = header.xpath('//img[contains(@itemprop, "image")]/@src')
        # description = header.xpath('//div[contains(@class, "recipe-header__description")]//text()').get()
        # time = {
        #     "prep": {
        #         'hrs': header.xpath('//span[contains(@class, "recipe-details__cooking-time-prep")]/'
        #                             'span[contains(@class, "hrs")]/text()').get(),
        #         'mins': header.xpath('//span[contains(@class, "recipe-details__cooking-time-prep")]/'
        #                      'span[contains(@class, "mins")]/text()').get(),
        #     },
        #     "cook": {
        #         'hrs': header.xpath('//span[contains(@class, "recipe-details__cooking-time-cook")]/'
        #                             'span[contains(@class, "hrs")]/text()').get(),
        #         'mins': header.xpath('//span[contains(@class, "recipe-details__cooking-time-cook")]/'
        #                              'span[contains(@class, "mins")]/text()').get(),
        #     }
        # }

        # difficulty = header.xpath('//section[contains(@class, "recipe-details__item--skill-level")]'
        #                           '/span[contains(@class, "recipe-details__text")]/text()').get()
        # servings = header.xpath('//section[contains(@class, "recipe-details__item--servings")]'
        #                           '/span[contains(@class, "recipe-details__text")]/text()').get()
        # # Here we gather available nutritional info and build the Nutrition object
        # nutrition_list = header.xpath('//ul[contains(@class, "nutrition")]')
        # kcal = nutrition_list.xpath('//span[contains(@itemprop, "calories")]/text()').get()
        # fat = nutrition_list.xpath('//span[contains(@itemprop, "fatContent")]/text()').get()
        # sat_fats = nutrition_list.xpath('//span[contains(@itemprop, "saturatedFatContent")]/text()').get()
        # carbs = nutrition_list.xpath('//span[contains(@itemprop, "carbohydrateContent")]/text()').get()
        # sugars = nutrition_list.xpath('//span[contains(@itemprop, "sugarContent")]/text()').get()
        # fibre = nutrition_list.xpath('//span[contains(@itemprop, "fiberContent")]/text()').get()
        # protein = nutrition_list.xpath('//span[contains(@itemprop, "proteinContent")]/text()').get()
        # salt = nutrition_list.xpath('//span[contains(@itemprop, "sodiumContent")]/text()').get()
        # nutrition_object = Nutrition(
        #     kcal, fat, sat_fats, carbs, sugars, fibre, protein, salt)

        # # Information from the details section includes ingredients and method
        # details = response.xpath('//div[contains(@class, "responsive-tabs")]')
        # # The full text of the ingredients will be in the content attribute of the li tag
        # ingredients = details.xpath('section[contains(@id, "recipe-ingredients")]//'
        #                             'div[contains(@class, "ingredients-list__content")]/ul/li/@content')

        # # TODO Check for final method step, sometimes the beeb offers a suggestion with a link to another recipe
        # method = details.xpath('section[contains(@id, "recipe-method")]//'
        #                        'div[contains(@class, "method")]/ol/li/p/text()')

        # recipe_object = Recipe(recipe_title.get(), attrib.get(), description, nutrition_object, ingredients.getall(),
        #                        method.getall(), time, difficulty, servings, img.get())

        # self, name, author, nutrition, ingredients, method
        return recipe_object.to_dict()
        pass
