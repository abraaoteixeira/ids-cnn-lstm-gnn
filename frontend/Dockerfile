# Stage 1: Build the React application
FROM node:20-alpine AS build

WORKDIR /app

# Copy package.json and package-lock.json from dashboard_v2
COPY dashboard_v2/package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY dashboard_v2/ ./

# Run build
RUN npm run build

# Stage 2: Serve using Nginx
FROM nginx:alpine

# Copy built assets from Stage 1 to Nginx HTML folder
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration file
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
