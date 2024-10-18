FROM node:16

WORKDIR /whatsapp_baileys

COPY package.json .

RUN npm install --force

COPY . .

CMD ["node", "index.js"]
