"""Known services and words that can never be a service or image name."""

# name -> (image, default tag, entry point, default port, YAML args)
SERVICES = {
    "nginx": ("docker.io/library/nginx", "1.27", "nginx", 80, '["-g", "daemon off;"]'),
    "redis": ("docker.io/library/redis", "7", "redis-server", 6379, "[]"),
    "postgres": ("docker.io/library/postgres", "16", "postgres", 5432, "[]"),
}

SKIP_NAMES = {
    "a",
    "an",
    "the",
    "to",
    "as",
    "on",
    "from",
    "into",
    "for",
    "service",
    "deployment",
    "container",
    "file",
    "yaml",
    "yml",
    "app",
    "application",
    "profile",
    "native",
    "device",
    "docker",
    "image",
    "using",
}
