# Here we use some code to calculate data values:

{
    "service": "yaml-api",
    "host": ".".join(["127", "0", "0", "1"]),
    "port": 8000 + 80,
    "debug": 1 > 2,
    "workers": 2 * 2,
    "allowed_origins": ["https://example.com"],
}
