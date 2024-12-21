import re
from flask import Flask, jsonify, request
import requests
import xml.etree.ElementTree as ET
from flask_cors import CORS
import openai
from dotenv import load_dotenv
import os
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)  # CORSを有効にする

# 天気予報APIのエンドポイント
WEATHER_API_URL = "https://weather.tsukumijima.net/api/forecast"
PRIMARY_AREA_URL = "https://weather.tsukumijima.net/primary_area.xml"


# トップページ
@app.route('/')
def home():
    return "Welcome to the API"

# 都道府県のリストを取得するAPI
@app.route('/api/prefectures', methods=['GET'])
def get_prefectures():
    response = requests.get(PRIMARY_AREA_URL)
    
    if response.status_code == 200:
        xml_data = response.content
        root = ET.fromstring(xml_data)
        
        prefectures = []
        
        for pref in root.findall('.//pref'):
            pref_title = pref.get('title')
            for city in pref.findall('city'):
                city_title = city.get('title')
                city_id = city.get('id')
                prefectures.append({
                    'prefecture': pref_title,
                    'city': city_title,
                    'id': city_id
                })
        
        return jsonify(prefectures=prefectures)
    else:
        return jsonify(error='Failed to fetch data'), 500

# 都道府県別の都市リストを取得して返す関数
def get_cities_by_prefecture(prefecture_code):
    response = requests.get(PRIMARY_AREA_URL)
    if response.status_code != 200:
        return []

    root = ET.fromstring(response.content)
    cities = []

    for pref in root.findall(".//pref[@title]"):
        if pref.attrib['id'] == prefecture_code:
            for city in pref.findall(".//city"):
                cities.append({"name": city.attrib['title'], "code": city.attrib['id']})
    return cities

# 天気情報を取得する関数
def get_weather(city_code):
    url = f"{WEATHER_API_URL}?city={city_code}"
    response = requests.get(url)
    if response.status_code != 200:
        return None

    try:
        root = ET.fromstring(response.content)
        weather_data = {
            'telop': root.find('forecast/telop').text,
            'temperature': {
                'max': {
                    'celsius': root.find('forecast/temperature/max/celsius').text
                },
                'min': {
                    'celsius': root.find('forecast/temperature/min/celsius').text
                }
            },
            # 'chanceOfRain': [
            #     {'value': root.find(f'forecast/chanceOfRain/{i}').text} for i in range(1, 5)
            # ],
            'chanceOfRain': {
                'T00_06': root.find('forecast/chanceOfRain/period[1]').text,
                'T06_12': root.find('forecast/chanceOfRain/period[2]').text,
                'T12_18': root.find('forecast/chanceOfRain/period[3]').text,
                'T18_24': root.find('forecast/chanceOfRain/period[4]').text,
            },
            'image': {
                'url': root.find('forecast/image/url').text
            }
        }
        return weather_data
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

# 都道府県に基づいた都市リストを返すエンドポイント
@app.route('/api/cities', methods=['GET'])
def cities():
    prefecture_code = request.args.get('prefecture_code')
    if not prefecture_code:
        return jsonify({"error": "Prefecture code is required"}), 400
    
    cities = get_cities_by_prefecture(prefecture_code)
    if not cities:
        return jsonify({"error": "No cities found for the given prefecture"}), 404
    
    return jsonify(cities)

# 天気情報を返すエンドポイント
@app.route('/api/weather', methods=['GET'])
def weather():
    city_code = request.args.get('city_code')
    if not city_code:
        return jsonify({"error": "City code is required"}), 400
    
    weather_data = get_weather(city_code)
    if weather_data is None:
        print("Failed to retrieve weather data.")
        return jsonify({"error": "Weather data not found"}), 404
    
    return jsonify(weather_data)

# OpenAI APIを使用して服装の提案を返すエンドポイント
@app.route('/api/gpt', methods=['POST'])
def gpt():
    try:
        data = request.get_json()
        weather_data = data.get('weather_data')
        scene = data.get('scene')

        if not weather_data or not scene:
            return jsonify({'error': '必要なデータが提供されていません'}), 400

        # 天気データから必要な情報を抽出
        forecast = weather_data['forecasts'][0]  # 'forecasts' 配列の最初の要素を使用

        chance_of_rain = forecast.get('chanceOfRain', None)

        # chance_of_rain が辞書形式か確認し、キーを使ってアクセスする
        if chance_of_rain and isinstance(chance_of_rain, dict):
            rain_chance_str = ', '.join([f"{key}: {value}" for key, value in chance_of_rain.items()])
        else:
            rain_chance_str = "降水確率のデータがありません。"

        # 天気情報を元にプロンプトを作成
        prompt = f"天気は{forecast['telop']}で、最高気温は{forecast['temperature']['max']['celsius']}℃、最低気温は{forecast['temperature']['min']['celsius']}℃です。" \
                 f"降水確率は{rain_chance_str}です。この天気に基づいて、30代の男性女性それぞれにおすすめの{scene}シーンに適したトレンドスタイルを提案してください。"

        load_dotenv(override=True) #環境変数を更新
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            print("Error: OpenAI APIキーが設定されていません.")

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたはファッションアドバイザーです。その日の天気とシーンに応じた服装を提案するプロフェッショナルです。"},
                {"role": "user", "content": prompt}
            ],
        )
        suggestion = response.choices[0].message.content
        # Markdown記法を削除するための処理
        plain_suggestion = re.sub(r'(\*\*|###|##|#)', '', suggestion)

        # Translatorを使用して日本語から英語に翻訳 (deep-translator使用)
        translated_suggestion = GoogleTranslator(source='ja', target='en').translate(plain_suggestion)
        translated_scene = GoogleTranslator(source='ja', target='en').translate(scene)

        # DALL-E 3で使用するプロンプトを生成
        image_prompt = (
            f"A minimalist, flat-style illustration featuring one Japanese man in his 30s and one Japanese woman "
            f"in her 30s standing next to each other. Both are dressed according to the following suggestion for a {translated_scene} scene: {translated_suggestion}. "
            "The outfits should be simple, modern, and stylish, with clear lines and soft, muted colors. The style should be similar to clean fashion illustrations "
            "commonly seen in Japanese fashion magazines or lookbooks. Use minimal shading, light textures, and bold, distinct colors. The characters should look fashionable "
            "but casual, and their outfits should match the weather and scene described. Both should be facing forward with gentle smiles on their faces. "
            "The background should be plain white. Make sure only one man and one woman are shown, with no additional characters. "
            'For any items mentioned in the suggestion with phrases like "if needed" (such as a light cardigan or a thin jacket), '
            "place them next to the person, aligned to the side, as optional items."
        )

        # フロントエンドにローディング中のレスポンスを早く返す
        jsonify({
            'loading_message': '生成AIが裏で今コーディネート中です',
            'suggestion': suggestion
        })

        # DALL-E 3で画像生成
        image_response = openai.Image.create(
            model="dall-e-3",
            prompt=image_prompt,
            n=1,
            size="1024x1024"
        )

        # 生成された画像URLを取得
        image_url = image_response['data'][0]['url']

        # 画像生成結果を返す
        return jsonify({
            'suggestion': suggestion,
            'image_url': image_url
        })

    except Exception as e:
        # その他のエラー
        print(f"サーバーエラー: {e}")
        return jsonify({'error': 'サーバー内部エラーが発生しました'}), 500

if __name__ == '__main__':
    app.run(debug=True)