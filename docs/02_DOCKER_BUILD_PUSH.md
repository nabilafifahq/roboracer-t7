# Docker Build and Push Guide

Use this when updating the stack image.

Important: do **not** log in to another student's Docker Hub account.

---

## 1) Choose your workflow

### A) Run the class-validated image only (most users)

You only need pull access:

```bash
docker pull nabilafifahq/roboracer-t7:main-latest
```

No Docker Hub login is required for public pull.

### B) Build and publish your own image (maintainers)

Use your own Docker Hub username:

```bash
export DOCKER_USER=<your_dockerhub_username>
export IMAGE=${DOCKER_USER}/roboracer-t7:main-latest
```

Then follow build/tag/push below.

---

## 2) Build locally

From repo root:

```bash
docker build -t roboracer-t7:main-latest -f docker/dockerfile .
```

---

## 3) Tag for Docker Hub

```bash
docker tag roboracer-t7:main-latest ${IMAGE}
```

---

## 4) Login and push (your account)

```bash
docker login
docker push ${IMAGE}
```

---

## 5) Verify digest (important)

After push, save the digest shown in terminal for release notes.

Example:

```text
main-latest: digest: sha256:...
```

---

## 6) Pull on car

If using class image:

```bash
docker pull nabilafifahq/roboracer-t7:main-latest
```

If using your own image:

```bash
docker pull ${IMAGE}
```
