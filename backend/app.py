import re
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI
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
    try:
        response = requests.get(PRIMARY_AREA_URL, timeout=10)
        response.raise_for_status()
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
    except requests.exceptions.RequestException as e:
        print(f"Error fetching prefectures: {e}")
        return jsonify(error="Failed to fetch prefecture data"), 500

# 都道府県別の都市リストを取得して返す関数
def get_cities_by_prefecture(prefecture_code):
    try:
        response = requests.get(PRIMARY_AREA_URL, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        cities = []

        for pref in root.findall(".//pref"):
            if pref.attrib['title'] == prefecture_code:
                for city in pref.findall("city"):
                    cities.append({"name": city.attrib['title'], "code": city.attrib['id']})
        return cities
    except requests.exceptions.RequestException as e:
        print(f"Error fetching cities: {e}")
        return []

# 天気情報を取得する関数
def get_weather(city_code):
    url = f"{WEATHER_API_URL}?city={city_code}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()  # JSONデータを解析

        # 必要なデータが存在するか確認
        if not data.get("forecasts"):
            print("No forecasts found in response.")
            return None

        weather_data = {
            'telop': data['forecasts'][0]['telop'],
            'temperature': {
                'max': {
                    'celsius': data['forecasts'][0]['temperature']['max']['celsius']
                } if data['forecasts'][0]['temperature']['max'] else None,
                'min': {
                    'celsius': data['forecasts'][0]['temperature']['min']['celsius']
                } if data['forecasts'][0]['temperature']['min'] else None,
            },
            'chanceOfRain': {
                'T00_06': data['forecasts'][0]['chanceOfRain']['T00_06'],
                'T06_12': data['forecasts'][0]['chanceOfRain']['T06_12'],
                'T12_18': data['forecasts'][0]['chanceOfRain']['T12_18'],
                'T18_24': data['forecasts'][0]['chanceOfRain']['T18_24'],
            },
            'image': {
                'url': data['forecasts'][0]['image']['url']
            }
        }
        return weather_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather: {e}")
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
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),  # This is the default and can be omitted
        )

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "あなたはファッションアドバイザーです。その日の天気とシーンに応じた服装を提案するプロフェッショナルです。"},
                {"role": "user", "content": prompt}
            ],
            model="gpt-4o-mini",
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
        response_loading = jsonify({
            'loading_message': '生成AIが裏で今コーディネート中です',
            'suggestion': translated_suggestion
        })

        # DALL-E 3で画像生成
        image_response = client.images.generate(
            model="dall-e-3",
            prompt=image_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        # 生成された画像URLを取得
        image_url = image_response.data[0].url

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
    app.run(host="0.0.0.0", port=5000)