#!/bin/bash

# Neurosynth Backend Smoke Tests
# 請將 YOUR_APP_URL 替換為您的實際 Render URL

BASE_URL="https://athenalin11-neurosynth-backend.onrender.com"

echo "🧪 開始 Smoke Tests..."
echo "📍 測試 URL: $BASE_URL"
echo ""

echo "✅ 測試 1: 健康檢查"
curl -s "$BASE_URL/" || echo "❌ 失敗"
echo ""

echo "✅ 測試 2: 圖片端點"
curl -s -I "$BASE_URL/img" | head -1
echo ""

echo "✅ 測試 3: 資料庫連接測試"
curl -s "$BASE_URL/test_db" | head -5
echo ""

echo "✅ 測試 4: 術語分離分析"
curl -s "$BASE_URL/dissociate/terms/posterior_cingulate/ventromedial_prefrontal" | head -5
echo ""

echo "✅ 測試 5: 座標分離分析"
curl -s "$BASE_URL/dissociate/locations/0_-52_26/-2_50_-6" | head -5
echo ""

echo "🎉 Smoke Tests 完成！"
