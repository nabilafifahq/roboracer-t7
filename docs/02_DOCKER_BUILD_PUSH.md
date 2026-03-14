# Docker Build and Push Guide

Use this when updating the stack image.

---

## 1) Build locally

From repo root:

```bash
docker build -t roboracer-t7:main-latest -f docker/dockerfile .
```

---

## 2) Tag for Docker Hub

```bash
docker tag roboracer-t7:main-latest nabilafifahq/roboracer-t7:main-latest
```

---

## 3) Login and push

```bash
docker login
docker push nabilafifahq/roboracer-t7:main-latest
```

---

## 4) Verify digest (important)

After push, save the digest shown in terminal for release notes.

Example:

```text
main-latest: digest: sha256:...
```

---

## 5) Pull on car

```bash
docker pull nabilafifahq/roboracer-t7:main-latest
```
