# modal-deploy

在 [Modal](https://modal.com) 上部署 Xray 代理服务。

## 前置条件

### Cloudflare

- 准备 **Cloudflare Argo Tunnel** 的 **Token**
- Argo 服务的 **内部访问地址** 为 `http://localhost:8080`

### Modal

1. 注册并登录 [Modal 官网](https://modal.com) 。

2. 右上角头像 → **Settings** → 左侧 **API Tokens** → **New Token**，创建 token，名称随意；记录下系统分配的命令，里面包含 **Token ID** 与 **Token Secret** 。

   ```bash
   modal token set --token-id ak-DVvVsBafuR5jwERY9c6bem --token-secret as-frL0MjzFDw7DLLe7Yxtry1
   ```

   注：以上 token 信息为示例信息，请生成自己的信息。

3. 在 Modal 控制台 **Secrets** 中创建 **Custom** 类型 Secret，名称使用默认的 `custom-secret` ，设置以下变量信息：
   | 变量 | 是否必填 | 含义 |
   |------|------|------|
   | U | ✔ | UUID（原生出口节点用户凭据） |
   | D | ✔ | Argo 域名（ARGO_DOMAIN） |
   | T | ✔ | Argo Tunnel Token（ARGO_TOKEN） |
   | E | ✖ | Modal 项目访问地址（endpoint），形如：`https://<modal_username>--<app_name>-main.modal.run`，如果填写，项目大概每 5 分钟会访问一次自身地址，保持有活跃流量 |
   | P | ✖ | Cloudflare WARP WireGuard 私钥。若配置，系统会自动派生 WARP 用户 UUID 并启用 WARP 出口分流 |


## GitHub Actions 部署

1. Fork 本仓库。

2. 进入 Fork 后的仓库 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，添加：
   - `MODAL_TOKEN_ID`：ak-DVvVsBafuR5jwERY9c6bem
   - `MODAL_TOKEN_SECRET`：as-frL0MjzFDw7DLLe7Yxtry1

3. 确认 **Actions** 已启用。

4. 在 **Actions** 中选择工作流 **Deploy Modal App** → **Run workflow**，可选填写：
   - **app_name**：可选，Modal App 名称；留空默认为 `vevc-app`。填写不同的名称可以同时部署并运行多个独立的应用。
   - **modal_secret_name**：可选，引用的 Modal Secret 名称；留空默认为 `custom-secret`。多应用需要各自独立配置（不同域名、UUID、Token）时，可在 Modal 创建不同的 Secret 并在此指定。
   - **modal_region**：可选，Modal 运行区域，多个用英文逗号分隔；留空表示不固定区域。区域列表见 [Region selection](https://modal.com/docs/guide/region-selection#region-options)。
   - **modal_nonpreemptible**：`false` / `true`，是否启用非抢占。说明见 [Non-preemptible Functions](https://modal.com/docs/guide/preemption#non-preemptible-functions)。

   如果介意 IP 全球漂移，性价比方案使用 **modal_region** 固定区域；高成本方案开启 **modal_nonpreemptible** 固定 IP。

## 获取订阅链接

部署成功后，访问下面地址查看订阅链接（返回内容为订阅信息的 Base64 编码）：

`https://<modal_username>--<app_name>-main.modal.run/<UUID>`

- `<modal_username>`：你的 Modal 用户名
- `<app_name>`：你的应用名称（默认为 `vevc-app`）
- `<UUID>`：你在对应 Modal Secret 中设置的 `U`

**节点输出逻辑说明**：
- **未配置 `P` 变量时**：返回 **2 个原生网络节点**
  - `modal-ws-argo`：VLESS-WS 协议（基于 Cloudflare Argo Tunnel，原生网络出口）
  - `modal-hy2-realm`：Hysteria 2 协议（基于 Realm NAT 穿透，原生网络出口）
- **已配置 `P` 变量时**：返回 **4 个节点**（2 个原生网络节点 + 2 个 WARP 出口分流节点）
  - 额外提供经由 Cloudflare WARP 出口分流的 `modal-ws-warp` 与 `modal-hy2-warp`

## 说明

- `MODAL_REGION` / `MODAL_NONPREEMPTIBLE` 为本项目约定名称，由 `main.py` 读取后传给 Modal；与 `MODAL_TOKEN_ID` 等 Modal 客户端内置鉴权变量含义不同。
- 各云平台与 Modal 计费、区域加价、非抢占加价以 [Modal 定价与文档](https://modal.com/pricing) 为准。
