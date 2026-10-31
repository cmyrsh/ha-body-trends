ARG BUILD_FROM=ghcr.io/home-assistant/base:3.21
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 py3-pip py3-numpy py3-scipy py3-statsmodels py3-pandas
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt
COPY app /app/app
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
