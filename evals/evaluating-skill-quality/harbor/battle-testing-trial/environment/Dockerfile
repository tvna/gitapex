FROM node:24-bookworm-slim

# node+npm baked in for the Harbor agent setup; curl for test tooling.
# (Measured: in-container apt egress to Ubuntu archives is slow here, so
# keep the apt payload minimal.)
RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app