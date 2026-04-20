# modal-deploy

在 [Modal](https://modal.com) 上部署 Xray 代理服务。

## 前置条件

### Cloudflare

- 准备 **Cloudflare Argo Tunnel** 的 **Token**

### Modal

1. 注册并登录 [Modal 官网](https://modal.com) 。

2. 右上角头像 → **Settings** → 左侧 **API Tokens** → **New Token**，创建 token，名称随意；记录下系统分配的命令，里面包含 **Token ID** 与 **Token Secret** 。

   ```bash
   modal token set --token-id ak-DVvVsBafuR5jwERY9c6bem --token-secret as-frL0MjzFDw7DLLe7Yxtry1
   ```

   注：以上 token 信息均为示例信息，请生成自己的信息。

3. 在 Modal 控制台 **Secrets** 中创建 **Custom** 类型 Secret，名称使用默认的 `custom-secret` ，设置以下必填变量信息：
   | 变量 | 是否必填 | 含义 |
   |------|------|------|
   | U | ✔ | UUID |
   | D | ✔ | Argo 域名（ARGO_DOMAIN） |
   | T | ✔ | Argo Tunnel Token（ARGO_TOKEN） |
   | E | ✖ | Modal 项目访问地址（endpoint），可以不填，形如：`https://<modal_username>--vevc-app-main.modal.run`，如果填写，项目大概每 5 分钟会访问一次自身地址，保持有活跃流量 |


## GitHub Actions 部署

1. Fork 本仓库。

2. 进入 Fork 后的仓库 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，添加：
   - `MODAL_TOKEN_ID`：ak-DVvVsBafuR5jwERY9c6bem
   - `MODAL_TOKEN_SECRET`：as-frL0MjzFDw7DLLe7Yxtry1

3. 确认 **Actions** 已启用。

4. 在 **Actions** 中选择工作流 **Modal Deploy** → **Run workflow**，可选填写：
   - **modal_region**：可选，Modal 运行区域，多个用英文逗号分隔；留空表示不固定区域。区域列表见 [Region selection](https://modal.com/docs/guide/region-selection#region-options)。
   - **modal_nonpreemptible**：`false` / `true`，是否启用非抢占。说明见 [Non-preemptible Functions](https://modal.com/docs/guide/preemption#non-preemptible-functions)。

   如果介意 IP 全球漂移，性价比方案使用 **modal_region** 固定区域；高成本方案开启 **modal_nonpreemptible** 固定 IP。

## 说明

- `MODAL_REGION` / `MODAL_NONPREEMPTIBLE` 为本项目约定名称，由 `main.py` 读取后传给 Modal；与 `MODAL_TOKEN_ID` 等 Modal 客户端内置鉴权变量含义不同。
- 各云平台与 Modal 计费、区域加价、非抢占加价以 [Modal 定价与文档](https://modal.com/pricing) 为准。
