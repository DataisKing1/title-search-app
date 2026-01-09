# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Declare build argument for Vite API URL (Railway passes env vars as build args)
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application (VITE_API_URL will be baked into the bundle)
RUN npm run build

# Production stage - use nginx for static files
FROM nginx:alpine AS runner

# Copy built files to nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Create nginx config template directory and file for dynamic port
RUN mkdir -p /etc/nginx/templates && \
    echo 'server { \
    listen ${PORT}; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/templates/default.conf.template

# Default port (Railway will override with PORT env var)
ENV PORT=80

# Start nginx with envsubst for dynamic port
CMD sh -c "envsubst '\$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"
