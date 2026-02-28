FROM nginx:alpine

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy site into nginx web root
COPY . /usr/share/nginx/html/

# Custom nginx config — serve index.html, handle 404 to index
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
