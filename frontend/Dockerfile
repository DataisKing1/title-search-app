# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage - use nginx for static files
FROM nginx:alpine AS runner

# Copy built files to nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Create nginx config template for dynamic port
RUN echo 'server { \
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
