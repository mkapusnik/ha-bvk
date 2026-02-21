FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install --omit=dev

COPY app.js index.js ./
COPY public ./public

ENV NODE_ENV=production

CMD ["node", "index.js"]
