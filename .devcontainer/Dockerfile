FROM mcr.microsoft.com/devcontainers/base:debian
ENV UV_INSTALL_DIR="/bin"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    uv self update

WORKDIR /app

ENV CONDA_DIR=/opt/conda
ENV PATH=$CONDA_DIR/bin:$PATH
ENV LD_LIBRARY_PATH=$CONDA_DIR/lib

RUN --mount=type=cache,dst=/root/.cache/ \
    wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && rm ~/miniconda.sh && \
    conda install -c conda-forge 'ffmpeg<7,>5' sox && ffmpeg -version && sox --version

COPY uv.toml  ./
RUN uv python install --preview --default && \
    mkdir /home/vscode/.cache && \
    chmod 777 /home/vscode/.cache
