# Image phát triển: chạy Vite dev server. Bản build + nginx cho triển khai làm ở Giai đoạn 11.
FROM node:22-alpine

WORKDIR /app

# Cài dependency trước để tận dụng cache của Docker khi chỉ đổi mã nguồn.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
