"use client";

import { useState } from 'react';
import prefecturesData from '../components/prefectures';
import ReactMarkdown from 'react-markdown';
import '../app/globals.css'; // TailwindCSSを使用するためにスタイルシートをインポート

const WeatherApp = () => {
  const [prefectureList, setPrefectureList] = useState(prefecturesData);
  const [cities, setCities] = useState([]);
  const [prefectureCode, setPrefectureCode] = useState('');
  const [cityCode, setCityCode] = useState('');
  const [selectedDate, setSelectedDate] = useState('tomorrow');
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [scene, setScene] = useState('casual');
  const [outfitSuggestion, setOutfitSuggestion] = useState(null);
  const [outfitLoading, setOutfitLoading] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [imageLoading, setImageLoading] = useState(false);

  // RenderのURLを環境変数から取得
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000";
  console.log("Backend URL:",backendUrl);

  const getCityName = () => {
    const selectedCity = cities.find(city => city.id === cityCode);
    return selectedCity ? selectedCity.name : '都市名が見つかりません';
  };

  const handleError = (message) => {
    setError(message);
    setOutfitSuggestion(null);
    setImageUrl('');
  };

  const handlePrefectureChange = (e) => {
    const selectedPrefecture = e.target.value;
    setPrefectureCode(selectedPrefecture);
    const selectedCities = prefectureList.find(pref => pref.code === selectedPrefecture)?.cities || [];
    setCities(selectedCities);
    setCityCode('');
  };

  const handleCityChange = (e) => {
    setCityCode(e.target.value);
  };

  const handleDateChange = (e) => {
    setSelectedDate(e.target.value);
  };

  const handleSceneChange = (e) => {
    setScene(e.target.value);
  };

  const fetchWeather = async () => {
    if (cityCode) {
      try {
        setLoading(true);
        const url = `https://weather.tsukumijima.net/api/forecast?city=${cityCode}`;
        const response = await fetch(url);

        if (!response.ok) {
          throw new Error("天気データの取得に失敗しました");
        }
        const weatherData = await response.json();
        setWeather(weatherData);
        setError(null);

        await fetchOutfitSuggestion(weatherData);

      } catch (error) {
        console.error('天気データの取得に失敗しました:', error);
        handleError('天気データの取得に失敗しました');
      } finally {
        setLoading(false);
      }
    } else {
      setError('');
    }
  };

  const getWeatherForSelectedDate = (data, date) => {
    const dateMapping = {
      today: 0,
      tomorrow: 1,
      dayAfterTomorrow: 2,
    };
    const index = dateMapping[date];
    return (index < data.forecasts.length) ? data.forecasts[index] : null;
  };

  const formatRainChance = (chanceOfRain) => {
    return (
      <div className="flex justify-between text-sm">
        <p>0-6時: {chanceOfRain['T00_06']}</p>
        <p>6-12時: {chanceOfRain['T06_12']}</p>
        <p>12-18時: {chanceOfRain['T12_18']}</p>
        <p>18-24時: {chanceOfRain['T18_24']}</p>
      </div>
    );
  };

  const fetchOutfitSuggestion = async (weatherData) => {
    try {
      setOutfitLoading(true);
      setImageLoading(true); 
      const response = await fetch(`${backendUrl}/api/gpt`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          weather_data: weatherData,
          scene: scene
        }),
      });

      if (!response.ok) {
        throw new Error(`サーバーエラー: ${response.status}`);
      }

      const result = await response.json();
      setOutfitSuggestion(result.suggestion || '服装提案を取得できませんでした。');
      setImageUrl(result.image_url || '');  

    } catch (error) {
      console.error('GPTリクエストのエラー:', error);
      setOutfitSuggestion('服装提案を取得できませんでした。');
      setImageUrl('');  
    } finally {
      setOutfitLoading(false);
      setImageLoading(false);  
    }
  };

  const selectedForecast = weather ? getWeatherForSelectedDate(weather, selectedDate) : null;

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4" style={{ fontFamily: "'Noto Sans JP', sans-serif" }}>
      {/* タイトル */}
      <div className="flex items-center justify-center w-full">
        <img src="/images/female.png" alt="女性の服装" className="w-16 h-16 mr-4" />
        <h1 className="text-3xl font-bold mb-2 text-black sticky top-0 bg-gray-100 z-10 p-4">
          あなたの服装予報をいたします
        </h1>
        <img src="/images/male.png" alt="男性の服装" className="w-16 h-16 ml-4" />
      </div>
  
      <div className="flex flex-col lg:flex-row justify-between w-full max-w-6xl space-x-0 lg:space-x-4 mt-8">
        {/* 左側：選択フォーム */}
        <div className="card bg-neutral-content shadow-lg p-4 w-full lg:w-1/3 min-h-[24rem] mb-4 lg:mb-0">
          {/* フォーム */}
          {/* Prefecture, City, Date, Scene inputs */}
          <div className="form-control mb-4">
            <label className="label text-black">
              <span className="label-text">都道府県を選択:</span>
            </label>
            <select className="select select-bordered w-full" onChange={handlePrefectureChange} value={prefectureCode}>
              <option value="">-- 都道府県を選択 --</option>
              {prefectureList.map((pref) => (
                <option key={pref.code} value={pref.code}>
                  {pref.name}
                </option>
              ))}
            </select>
          </div>
  
          <div className="form-control mb-4">
            <label className="label text-black">
              <span className="label-text">都市を選択:</span>
            </label>
            <select className="select select-bordered w-full" onChange={handleCityChange} disabled={!prefectureCode} value={cityCode}>
              <option value="">-- 都市を選択 --</option>
              {cities.map((city) => (
                <option key={city.id} value={city.id}>
                  {city.name}
                </option>
              ))}
            </select>
          </div>
  
          <div className="form-control mb-4">
            <label className="label text-black">
              <span className="label-text">日付を選択:</span>
            </label>
            <select className="select select-bordered w-full" onChange={handleDateChange} value={selectedDate}>
              <option value="today">今日</option>
              <option value="tomorrow">明日</option>
              <option value="dayAfterTomorrow">明後日</option>
            </select>
          </div>
  
          <div className="form-control mb-4">
            <label className="label text-black">
              <span className="label-text">シーンを選択:</span>
            </label>
            <select className="select select-bordered w-full" onChange={handleSceneChange} value={scene}>
              <option value="casual">カジュアル</option>
              <option value="business">ビジネス</option>
              <option value="formal">フォーマル</option>
            </select>
          </div>
  
          {/* 調べるボタン */}
          <button onClick={fetchWeather} className="btn w-full bg-base-200 text-black mt-4">
            調べる
          </button>
        </div>
  
        {/* 右側：天気情報 */}
        <div className="card bg-neutral-content shadow-lg p-4 w-full lg:w-2/3 h-auto">
          {weather && (
            <div className="mt-4 text-black flex items-center justify-between">
              <p className="text-xl font-semibold">
                {getCityName()}の{selectedDate === 'today' ? '今日' : selectedDate === 'tomorrow' ? '明日' : '明後日'}の天気
              </p>
            </div>
          )}
  
          {/* 天気情報の詳細 */}
          {selectedForecast && (
            <div className="mt-2">
              {/* 天気アイコンと天気テキストを横並びに表示 */}
              <div className="flex items-center">
                <p className="mr-2">天気: {selectedForecast.telop}</p>
                {selectedForecast.image && (
                  <img src={selectedForecast.image.url} alt="天気アイコン" className="w-12 h-12" />
                )}
                </div>
                <p>最高気温: {selectedForecast.temperature?.max?.celsius}°C</p>
                <p>最低気温: {selectedForecast.temperature?.min?.celsius}°C</p>
                <div className="mt-2">
                  <p>降水確率:</p>
                  {selectedForecast.chanceOfRain ? formatRainChance(selectedForecast.chanceOfRain) : '情報がありません'}
                </div>
              </div>
            )}
  
          {/* エラーメッセージ */}
          {error && <p className="text-red-500">{error}</p>}
  
          {/* ローディングメッセージ */}
          {loading && <p className="text-accent-content"></p>}
  
          {/* DALL-E画像 */}
          {imageLoading ? (
            <p className="text-accent-content mt-8">素敵な洋服を探しています...</p> // 天気情報と余白を追加
          ) : imageUrl ? (
            <div>
              <img src={imageUrl} alt="服装提案画像" className="mt-4 w-64 h-auto" />
              <p className="text-left text-black font-semibold mt-2">コーディネート参考</p> {/* 画像の下にテキスト追加 下である必要ある？*/}
            </div>
          ) : null}

        </div>
      </div>
  
      {/* カードで服装提案を表示 */}
      <div className="card bg-neutral-content shadow-lg p-4 w-full max-w-6xl mt-4">
        {outfitLoading ? (
          <p className="text-accent-content">コーディネートを考案中...</p>
        ) : outfitSuggestion ? (
          <div className="mt-4">
            <h2 className="text-xl font-semibold">服装のご提案:</h2>
            <div className="mb-4">
              <ReactMarkdown>{outfitSuggestion.split('\n\n')[0]}</ReactMarkdown>
            </div>
            <div className="border-t-2 border-gray-300 pt-4">
              <h3 className="font-bold text-lg">男性のスタイル:</h3>
              <ReactMarkdown>{outfitSuggestion.split('\n\n')[1]}</ReactMarkdown>
            </div>
            <div className="border-t-2 border-gray-300 pt-4 mt-4">
              <h3 className="font-bold text-lg">女性のスタイル:</h3>
              <ReactMarkdown>{outfitSuggestion.split('\n\n')[2]}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <p className="mt-4">服装のご提案内容はこちらに表示されます。</p>
        )}
      </div>
    </div>
  );  
};

export default WeatherApp;
