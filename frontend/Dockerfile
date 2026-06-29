FROM node:22.12-bullseye  AS build
WORKDIR /usr/src/app
COPY . /usr/src/app
RUN npm install
ARG configuration=production
RUN npm run build -- --configuration=${configuration} --output-hashing=all --base-href /

FROM nginx:1.19.6
COPY ./nginx/default.conf /etc/nginx/conf.d/
COPY --from=build /usr/src/app/dist/ecert-crd13-frontend /usr/share/nginx/html


