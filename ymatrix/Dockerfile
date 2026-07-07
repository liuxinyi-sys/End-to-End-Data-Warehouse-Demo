FROM ubuntu:20.04

LABEL description="MatrixDB Community Edition for YMatrix DW Demo"

COPY matrixdb5_5.2.1+community-1_amd64.deb /tmp/
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y         /tmp/matrixdb5_5.2.1+community-1_amd64.deb         sudo     && rm -f /tmp/matrixdb5_5.2.1+community-1_amd64.deb     && apt-get clean     && rm -rf /var/lib/apt/lists/*     && chmod +x /docker-entrypoint.sh

VOLUME /var/lib/matrixdb
EXPOSE 5432 8090

ENTRYPOINT ["/docker-entrypoint.sh"]
