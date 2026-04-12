FROM node:20-slim

WORKDIR /app

COPY scout-ui/package.json scout-ui/package-lock.json* ./
RUN npm install

COPY scout-ui/ .

ARG EXPO_PUBLIC_API_URL=http://localhost:8000
ENV EXPO_PUBLIC_API_URL=$EXPO_PUBLIC_API_URL

RUN npx expo export --platform web

RUN npm install -g serve

EXPOSE 3000
CMD ["serve", "dist", "-s", "-l", "tcp://0.0.0.0:3000"]
