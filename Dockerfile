FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN python build/build_zwo.py > /dev/null && python build/build_dash.py
ENV HOST=0.0.0.0 PORT=8080 DATA_DIR=/data
VOLUME /data
EXPOSE 8080
USER nobody
CMD ["python", "server/server.py"]
