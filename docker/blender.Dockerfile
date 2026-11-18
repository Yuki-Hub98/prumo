# Blender LTS headless para os renders (CLAUDE.md §10). Versões fixadas por ARG.
# Uso: make blender-imagem  ·  o orquestrador roda: docker run --rm interiores-blender:<versão> ...
ARG DEBIAN_TAG=bookworm-20251117-slim
FROM debian:${DEBIAN_TAG}

ARG BLENDER_SERIE=4.5
ARG BLENDER_VERSION=4.5.16

# bibliotecas que o Blender pede mesmo sem tela (X11/GL são carregadas na inicialização)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl xz-utils \
      libx11-6 libxext6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 \
      libsm6 libice6 libgl1 libegl1 libglu1-mesa \
 && rm -rf /var/lib/apt/lists/*

# baixa do site oficial e confere o sha256 publicado junto
RUN set -eu; \
    base="https://download.blender.org/release/Blender${BLENDER_SERIE}"; \
    arquivo="blender-${BLENDER_VERSION}-linux-x64.tar.xz"; \
    cd /tmp; \
    curl -fsSLO "${base}/${arquivo}"; \
    curl -fsSL "${base}/blender-${BLENDER_VERSION}.sha256" | grep " ${arquivo}\$" | sha256sum -c -; \
    tar -xJf "${arquivo}" -C /opt; \
    rm "${arquivo}"; \
    ln -s "/opt/blender-${BLENDER_VERSION}-linux-x64/blender" /usr/local/bin/blender

ENV HOME=/tmp
WORKDIR /trabalho
ENTRYPOINT ["blender", "--background", "--factory-startup"]
