FROM node:20-alpine

WORKDIR /app

COPY package.json /app/package.json
RUN npm install

COPY . /app
COPY public/LICENSE public/NOTICE public/THIRD_PARTY_LICENSES.md /app/

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
