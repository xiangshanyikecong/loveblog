FROM node:20.20-alpine3.22

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app
COPY public/NOTICE public/THIRD_PARTY_LICENSES.md /app/

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
