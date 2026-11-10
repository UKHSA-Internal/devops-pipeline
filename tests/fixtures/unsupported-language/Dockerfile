FROM scratch

LABEL org.opencontainers.image.title="unsupported-language"

# A real layer is required: `docker save` fails with "empty export" for images without layers.
COPY README.md /README.md
