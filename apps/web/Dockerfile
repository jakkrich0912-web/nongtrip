# หน้าเว็บ: build ด้วย Vite แล้วให้ nginx เสิร์ฟ และส่งต่อ /api ไปที่บริการ api (build จากโฟลเดอร์รากของ repo)
FROM node:22-alpine AS build
WORKDIR /src

COPY apps/web/package.json apps/web/package-lock.json apps/web/
RUN cd apps/web && npm ci --no-audit --no-fund

COPY apps/web apps/web
# หน้าเว็บอ่านข้อมูลสถานที่ที่ตรวจที่มาแล้วจาก services/places/data (ดู vite.config.js)
COPY services/places/data/places.json services/places/data/places_all_provinces.json services/places/data/
RUN cd apps/web && npm run build

FROM nginx:1.27-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
EXPOSE 80
