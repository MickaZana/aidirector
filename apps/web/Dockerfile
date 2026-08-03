FROM node:20-alpine

WORKDIR /app
COPY . .

WORKDIR /app/apps/web
RUN npm install --include=dev
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
