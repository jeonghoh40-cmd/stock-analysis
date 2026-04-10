# ---- Stage 1: Build Next.js ----
FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Stage 2: Production ----
FROM node:20-slim

# Python 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Node.js 앱 복사
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public
COPY --from=builder /app/scripts ./scripts
COPY --from=builder /app/next.config.ts ./next.config.ts

# vc_investment_analyzer 복사 및 Python 의존성 설치
COPY vc_investment_analyzer /opt/analyzer
RUN python3 -m venv /opt/analyzer/venv && \
    /opt/analyzer/venv/bin/pip install --no-cache-dir -r /opt/analyzer/config/requirements.txt 2>/dev/null || \
    /opt/analyzer/venv/bin/pip install --no-cache-dir -r /opt/analyzer/requirements.txt

# 데이터 디렉토리
RUN mkdir -p /data/reports /data/uploads

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
ENV ANALYZER_ROOT=/opt/analyzer
ENV PYTHON_BIN=/opt/analyzer/venv/bin/python3
ENV UPLOAD_ROOT=/data/uploads

EXPOSE 3000

CMD ["npm", "start"]
