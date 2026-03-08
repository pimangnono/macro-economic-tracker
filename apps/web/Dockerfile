FROM node:20-slim

WORKDIR /app

COPY apps/web/package.json /app/package.json
COPY apps/web/tsconfig.json /app/tsconfig.json
COPY apps/web/next.config.ts /app/next.config.ts
COPY apps/web/next-env.d.ts /app/next-env.d.ts

RUN npm install

COPY apps/web /app

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]

