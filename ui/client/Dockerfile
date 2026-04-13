FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
# Allow Vite to bind to all interfaces inside Docker
CMD ["npx", "vite", "--host", "0.0.0.0"]
