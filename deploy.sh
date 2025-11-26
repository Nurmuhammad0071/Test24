#!/bin/bash

# Test24 Backend Auto-Deploy Script
# Bu script serverga Git orqali deploy qiladi

set -e

SERVER_IP="${SERVER_IP:-37.60.247.170}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_PASSWORD="${SERVER_PASSWORD:-}"
GIT_TOKEN="${GIT_TOKEN:-}"
PROJECT_PATH="/opt/test24_backend"
SERVICE_NAME="test24_backend-backend"

if [ -z "$SERVER_PASSWORD" ] || [ -z "$GIT_TOKEN" ]; then
    echo "❌ Xatolik: SERVER_PASSWORD va GIT_TOKEN environment variable'larini o'rnating"
    echo "Misol: export SERVER_PASSWORD='your_password' && export GIT_TOKEN='your_token' && ./deploy.sh"
    exit 1
fi

echo "🚀 Test24 Backend Deploy boshlandi..."

# 1. Git'ga push qilish (agar o'zgarishlar bo'lsa)
if [ -n "$(git status --porcelain)" ]; then
    echo "📝 O'zgarishlar topildi, Git'ga commit qilinmoqda..."
    git add -A
    git commit -m "Auto-deploy: $(date '+%Y-%m-%d %H:%M:%S')" || echo "Commit qilishda xatolik (ehtimol o'zgarishlar yo'q)"
    git push https://${GIT_TOKEN}@github.com/Nurmuhammad0071/Test24.git main || echo "Push qilishda xatolik"
fi

# 2. Serverga ulanish va Git pull
echo "📥 Serverda Git pull qilinmoqda..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << EOF
    cd ${PROJECT_PATH}
    git pull https://${GIT_TOKEN}@github.com/Nurmuhammad0071/Test24.git main
EOF

# 3. Dependencies yangilash
echo "📦 Dependencies yangilanmoqda..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << EOF
    cd ${PROJECT_PATH}
    source venv/bin/activate
    pip install -r requirements.txt --quiet
EOF

# 4. Migrations bajarish
echo "🗄️  Migrations bajarilmoqda..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << EOF
    cd ${PROJECT_PATH}
    source venv/bin/activate
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
EOF

# 5. Service restart
echo "🔄 Service qayta ishga tushirilmoqda..."
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} << EOF
    systemctl restart ${SERVICE_NAME}
    sleep 2
    systemctl status ${SERVICE_NAME} --no-pager | head -10
EOF

echo "✅ Deploy muvaffaqiyatli yakunlandi!"
echo "🌐 Service: http://${SERVER_IP}:8001"
echo "📊 Status: sshpass -p '$SERVER_PASSWORD' ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} 'systemctl status ${SERVICE_NAME}'"

