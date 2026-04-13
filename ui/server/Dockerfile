FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5000
# Use nodemon with --legacy-watch for file polling (required on Windows Docker volumes)
CMD ["npm", "run", "docker"]
