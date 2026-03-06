# Sử dụng image chính thức của AWS Lambda cho Python
FROM public.ecr.aws/lambda/python:3.11

# Cài đặt công cụ build cần thiết cho các thư viện C++ (ChromaDB)
RUN yum update -y && \
    yum install -y gcc gcc-c++ make shadow-utils

# Sao chép và cài đặt các thư viện Python
COPY requirements.txt .

COPY ./db /var/task/db
COPY ./data/policy.pdf /var/task/data/policy.pdf

# Nâng cấp pip và cài đặt thư viện
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn vào thư mục TASK_ROOT
COPY . ${LAMBDA_TASK_ROOT}

# Chỉ định handler (file: main, biến: handler)
CMD [ "main.handler" ]