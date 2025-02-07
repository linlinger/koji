# 玩起来

## Koji Server端的配置


Koji 是 Fedora 的包编译管理工具。功能十分强大. 使用 Mock 作为底层. 用于批量编译软件包。


### 架构

1. 我们都知道 rpmbuild 是 Linux 平台下一款编译 RPM 包的工具. 而 Mock 则是在 rpmbuild 之上封装了一层（查看 Mock 的使用方法）. 利用 yum 来下载一个最小的系统环境. 从而实验跨系统的编译工作。而 Koji 则是在 Mock 之上再次进行了封装. 由 Koji Server 统一管理. 将大量编译任务交给若干个安装了 Mock 的编译机来完成. 这些编译机也叫 Koji Builder。

2. 本例使用两台服务器（服务端+编译机）配合完成. 本例将服务端称之为 Koji Server. 将编译机称之为 Koji Builder。

3. 本例中的 Koji Server 由 Postgresql 数据库（用来记录软件包的信息）、KojiHub（主程序）、KojiWeb（依赖于Httpd） 等组件组成。Kojira 用于管理和维护yum库. 装在哪里都行。本文中的实例是将 Kojira 与 KojiHub 装在同一台服务器上。

4. 本例中的 Koji Builder 运行着 Kojid 这个编译守护程序. 以及底层的 Mock。

5. KojiHub 是整个体系的核心. 通过 XML-RPC 运行于 Apache 的 mod_python 模块下。KojiHub 采用被动方式. 仅仅接受 XML-RPC 请求. 依赖编译守护模块和其他模块来进行交互。这意味着. 无须在 KojiHub 里指定 Koji Builder 的IP地址信息. 因为 KojiHub 是被动通信的. 需要 Koji Builder 主动与之“联系”。 koji 是一个用 python 写的程序. 用户通过 koji 命令. 来查询信息或者执行编译工作。

6. Koji 各组件之间的通信使用SSL证书. 所以本文的第一步就是为各组件创建证书。



### 软件包组织形式：Tags 和 Targets

要正常使用 Koji. 必须理解 Tags 和 Targets 的含义。

Koji 用 tag 组织软件包. 一个 tag 可以理解为一个大的软件分类. 例如 el6 平台下有很多软件包. 而 el6 就是一个 tag。正因为如此. 一个 tag 可以作为一个 yum 仓库。

1. tag 保存在数据库中而不是磁盘文件系统中. 每个 tag 有它自己的软件包列表（软件包列表可以被其他的 tag 继承）
2. 我们可以根据 tag 为软件包设置不同的所有者（所有者关系也可以被其他 tag 继承）
3. 当您编译软件包时. 您应该指定一个 target 而不是一个 tag

一个 target 表明了软件包的编译过程应该在哪里进行. 编译生成的软件包应该放入哪个 tag 中

```
$ koji list-targets
$ koji list-targets --name fc19
$ koji list-targets --name el6

Name                           Buildroot                      Destination
-------------------------------------------------------------------------------
el6                            el6-build                      el6
```

![20220808_110306_29](image/20220808_110306_29.png)

这告诉您利用 el6 这个 target 编译软件包时. 编译环境由 el6-build 这个 tag 中的软件包构成. 编译生成的软件包将放入 el6 这个 tag 中。重要！必务理解！

查看 tag 中的软件包列表

```
$ koji list-tags
$ koji list-pkgs --tag fc19
$ koji list-pkgs --tag el6
```


### 准备工作

安装第三方软件库EPEL. 根据系统版本打开相应的链接：

查找“epel”. 应该会找到一个“epel-release-X-X.noarch.rpm”的软件包。下载. 安装之。

### 创建 koji证书
由于创建证书的过程是在 koji server 端进行的. 因此这部分配置也写在 koji server 端。

创建SSL配置文件

```
[root@os1 ~]# yum install openssl openssl-devel
[root@os1 ~]# mkdir /etc/pki/koji/ &&  touch /etc/pki/koji/ssl.cnf
```

修改配置文件 /etc/pki/koji/ssl.cnf
```
HOME                    = .
RANDFILE                = .rand

[ca]
default_ca              = ca_default

[ca_default]
dir                     = .
certs                   = $dir/certs
crl_dir                 = $dir/crl
database                = $dir/index.txt
new_certs_dir           = $dir/newcerts
certificate             = $dir/%s_ca_cert.pem
private_key             = $dir/private/%s_ca_key.pem
serial                  = $dir/serial
crl                     = $dir/crl.pem
x509_extensions         = usr_cert
name_opt                = ca_default
cert_opt                = ca_default
default_days            = 3650
default_crl_days        = 30
default_md              = sha256
preserve                = no
policy                  = policy_match

[policy_match]
countryName             = match
stateOrProvinceName     = match
organizationName        = match
organizationalUnitName  = optional
commonName              = supplied
emailAddress            = optional

[req]
default_bits            = 3072
default_keyfile         = privkey.pem
distinguished_name      = req_distinguished_name
attributes              = req_attributes
x509_extensions         = v3_ca # The extentions to add to the self signed cert
string_mask             = MASK:0x2002

[req_distinguished_name]
countryName                     = Country Name (2 letter code)
countryName_default             = CN
countryName_min                 = 2
countryName_max                 = 2
stateOrProvinceName             = State or Province Name (full name)
stateOrProvinceName_default     = Jiangsu
localityName                    = Locality Name (eg, city)
localityName_default            = Nanjing
0.organizationName              = Organization Name (eg, company)
0.organizationName_default      = Qingsong
organizationalUnitName          = Organizational Unit Name (eg, section)
commonName                      = Common Name (eg, your name or your server\'s hostname)
commonName_max                  = 64
emailAddress                    = Email Address
emailAddress_default            = linyx@stp.net.cn
emailAddress_max                = 64

[req_attributes]
challengePassword               = A challenge password
challengePassword_min           = 4
challengePassword_max           = 20
unstructuredName                = An optional company name

[usr_cert]
basicConstraints                = CA:FALSE
nsComment                       = "OpenSSL Generated Certificate"
subjectKeyIdentifier            = hash
authorityKeyIdentifier          = keyid,issuer:always

[v3_ca]
subjectKeyIdentifier            = hash
authorityKeyIdentifier          = keyid:always,issuer:always
basicConstraints                = CA:true
```

创建CA认证中心

创建CA认证中心,需要首先为CA创建一个RSA私钥
```
[root@os1 ~]# cd /etc/pki/koji/
[root@os1 koji]# mkdir {certs,private}
[root@os1 koji]# touch index.txt
[root@os1 koji]# echo 01 > serial
[root@os1 koji]# caname=ca.stplinux.com
[root@os1 koji]# dd if=/dev/urandom of=/etc/pki/koji/.rand bs=256 count=1
[root@os1 koji]# openssl genrsa -out private/${caname}_ca_cert.key 3072
[root@os1 koji]# openssl req -config ssl.cnf -new -x509 -days 3650 -sha256 -key private/${caname}_ca_cert.key -out ${caname}_ca_cert.crt -extensions v3_ca
#服务器证书的 Common Name（公用名）必须与颁发者的域不同。 例如，在本例中，颁发者的 CN 是ca.stplinux.com，服务器证书的 CN 是 koji.qslinux.com
```

创建用户证书

创建koji各组件、koji-builder需要的证书

```
caname=ca.stplinux.com
for user in kojiweb kojihub kojira kojibuilder1 kojibuilder2 kojibuilder3 ;
do
    echo "*****************************************************"
    echo 
    echo "      Setting up certificate for user ${user}        "
    echo 
    echo "*****************************************************"
    openssl genrsa -out certs/${user}.key 2048
    openssl req -config ssl.cnf -new -nodes -out certs/${user}.csr -key certs/${user}.key
    openssl ca -config ssl.cnf -keyfile private/${caname}_ca_cert.key -cert ${caname}_ca_cert.crt -out certs/${user}.crt -outdir certs -infiles certs/${user}.csr
    cat certs/${user}.crt certs/${user}.key > ${user}.pem
done
```

注意：当kojihub和kojiweb安装在同一台机器上时设置为同一个 Common Name. 别的Common Name 写用户名，比如 kojira,kojid [y/n]选y. 其它直接回车

创建koji管理员和koji提交者需要的证书
```
caname=ca.stplinux.com
for user in kojiadmin kojiuser ;
do
    echo "*****************************************************"
    echo 
    echo "      Setting up certificate for koji user ${user}        "
    echo 
    echo "*****************************************************"
    openssl genrsa -out certs/${user}.key 3072
    openssl req -config ssl.cnf -new -nodes -out certs/${user}.csr -key certs/${user}.key
    openssl ca -config ssl.cnf -keyfile private/${caname}_ca_cert.key -cert ${caname}_ca_cert.crt -out certs/${user}.crt -outdir certs -infiles certs/${user}.csr
    cat certs/${user}.crt certs/${user}.key > ${user}.pem
    openssl pkcs12 -export -inkey certs/${user}.key -in certs/${user}.crt -CAfile ${caname}_ca_cert.crt -out certs/${user}_browser_cert.p12
    echo "*****************************************************"
    echo 
    echo "  Browser certificate for user ${user} is generated  "
    echo "      at certs/${user}_browser_cert.p12"
    echo 
    echo "*****************************************************"
done
```
注意： Common Name字段依次输入kojiadmin、kojiuser。此处的Common Name用于后续验证，因此要写用户名

### koji Server 端相关准备（创建用户、准备证书、配置Koji命令行程序、配置Postgresql数据库）

```
[root@os1 ~]# dnf install -y python3-pyOpenSSL python3-mod_wsgi postgresql-plpython3 python3-kerberos python3-cheetah python3-multilib httpd tmux openssl telnet ca-certificates mod_ssl postgresql-server koji koji-hub koji-hub-plugins koji-builder koji-builder-plugins koji-web koji-utils python3-koji-cli-plugins python3-koji-hub-plugins createrepo python3-mod_wsgi sqlite python3-librepo net-tools
```

2.1 创建用户. 并为用户准备证书
不建议使用 root 用户. 本例中我们建立一个名为 kojiadmin 的用户来管理 koji

```
[root@os1 ~]# useradd kojiadmin
[root@os1 ~]# su - kojiadmin
[kojiadmin@os1 ~]# mkdir ~/.koji
[kojiadmin@os1 ~]# cp -pv /etc/pki/koji/kojiadmin.pem ~/.koji/client.crt
[kojiadmin@os1 ~]# cp -pv /etc/pki/koji/ca.stplinux.com_ca_cert.crt ~/.koji/clientca.crt
[kojiadmin@os1 ~]# cp -pv /etc/pki/koji/ca.stplinux.com_ca_cert.crt ~/.koji/serverca.crt
[kojiadmin@os1 ~]# exit
```

修改 koji 主配置文件

koji 命令行程序默认使用 /etc/koji.conf 配置文件. 但是每个用户的 ~/.koji/config 文件会覆盖全局文件的设置. 如果您想针对每个用户进行不同的配置. 请将 /etc/koji.conf 拷贝到 ~/.koji/config。

修改配置文件 /etc/koji.conf

```
[koji]
server = http://koji.qslinux.com/kojihub
weburl = http://koji.qslinux.com/koji
topurl = http://koji.qslinux.com/kojifiles/
topdir = /mnt/koji
authtype = ssl
cert = ~/.koji/client.crt
ca = ~/.koji/clientca.crt
serverca = ~/.koji/serverca.crt
```

配置 Postgresql 数据库

PostgreSQL Server 配置文件列表

```
/var/lib/pgsql/data/pg_hba.conf
/var/lib/pgsql/data/postgresql.conf
/var/lib/pgsql/data/pg_hba.conf
```

````
[root@os1 ~]# yum install postgresql-server
[root@os1 ~]# useradd postgres
[root@os1 ~]# service postgresql initdb
[root@os1 ~]# systemctl enable postgresql --now
[root@os1 ~]# sudo systemctl enable --now koji-sweep-db.timer
```

创建系统 koji 用户并清空密码

```
[root@os1 ~]# useradd koji && passwd -d koji
```

在 PostgreSQL 中创建一个名为 koji 的帐号. 并初始化数据库
```
[root@os1 ~]# su - postgres
-bash-4.1$ createuser koji    #当询问到y/n. 全部选n
-bash-4.1$ createdb -O koji koji  #创建一个名为koji的数据库. 并由koji用户来管理. 删除用dropdb
-bash-4.1$ exit
[root@os1 ~]# su - koji
[koji@os1 ~]# psql koji koji < /usr/share/doc/koji*/docs/schema.sql
[koji@os1 ~]# exit
```

设置数据库 koji 用户访问 Postgresql 数据库权限
本例中. kojiweb和kojihub都是在本地localhost上运行。修改配置文件 /var/lib/pgsql/data/pg_hba.conf

手动添加这一行

```
host    koji        koji        127.0.0.1/32          trust
```

修改以下三行. 注意修改trust

```
local   all         all                               trust
host    all         all         127.0.0.1/32          trust
host    all         all         ::1/128               trust
```

应用改变

```
[root@os1 ~]# su - postgres
-bash-4.1$ pg_ctl reload -D /var/lib/pgsql/data
-bash-4.1$ exit
```

在 PostgreSQL 数据库中添加系统管理员信息. 然后 kojiadmin 用户才可以调用 koji add-host 等命令
```
[root@os1 ~]# su - koji
[koji@os1 ~]# psql 
insert into users (name, password, status, usertype) values ('kojiadmin', '', 0, 0);
select * from users;       # 找到kojiadmin的user id. 本例中user_id=1
insert into user_perms (user_id, perm_id,creator_id) values (1, 1, 1);


select * from users;
insert into user_perms (user_id, perm_id,creator_id) values (1, 1, 1);
select * from user_perms;

\q
```

### koji Server 端相关配置（KojiHub、Kojiweb）

KojiHub的配置

```
[root@os1 ~]# yum install koji-hub httpd mod_ssl mod_python
```

Koji Hub 配置文件列表

```
/etc/httpd/conf/httpd.conf
/etc/httpd/conf.d/kojihub.conf
/etc/httpd/conf.d/ssl.conf (如果采用 ssl 认证机制)
```
修改配置文件 /etc/httpd/conf.d/kojihub.conf. 添加如下几行
```
<Location /kojihub>
SSLOptions +StdEnvVars
</Location>
<Location /koji/login>
SSLOptions +StdEnvVars
</Location>

Alias /packages/ /mnt/koji/packages/
<Directory "/mnt/koji/packages">
Options Indexes
AllowOverride None
Order allow,deny
Allow from all
</Directory>
```
#以下选项可能有. 但需要去掉注释
```
<Location /kojihub/ssllogin>
SSLVerifyClient require
SSLVerifyDepth 10
SSLOptions +StdEnvVars
</Location>
```

修改配置文件 /etc/koji-hub/hub.conf

```
DBName = koji
DBUser = koji
#DBHost = localhost
#DBPass = 密码字符串
KojiDir = /mnt/koji
...
DNUsernameComponent = CN
ProxyDNs = /C=CN /ST=Jiangsu /L=Nanjing /O=Qingsong /CN=koji /emailAddress=linyx@stp.net.cn
...
KojiWebURL = http://koji.qslinux.com/koji
```
其中 ProxyDNs 和 kojiweb 认证文件的 DirName 字段一样。

修改配置文件 /etc/httpd/conf.d/ssl.conf

```
SSLCertificateFile /etc/pki/koji/certs/kojihub.crt
SSLCertificateKeyFile /etc/pki/koji/certs/kojihub.key
SSLCertificateChainFile /etc/pki/koji/ca.stplinux.com_ca_cert.crt
SSLCACertificateFile /etc/pki/koji/ca.stplinux.com_ca_cert.crt
SSLVerifyClient require
SSLVerifyDepth  10
```

提示. 请注释掉原有配置项（如SSLCertificateKeyFile等）. 否则Apache不能启动。为了系统能正常使用. 请停用selinux。

修改apache的性能
为了避免服务器负载过重甚至崩溃. 强烈建议将配置文件 httpd.conf 中两个对 MaxRequestsPerChild 进行设置的地方修改为合理的数值(当这个配置项的值为100时. 在重新启动 apache 服务前. httpd 进程能够占用到 75MB 内存)。
```
<IfModule prefork.c>
…
MaxRequestsPerChild 100
</IfModule>
<IfModule worker.c>
…
MaxRequestsPerChild 100
</IfModule>
```

###  Koji 文件系统设置
在前面 kojihub.conf 文件的配置过程中. 我们设置 KojiDir 的路径为 /mnt/koji。

```
[root@os1 ~]# mkdir /mnt/koji
[root@os1 ~]# cd /mnt/koji
[root@os1 ~]# mkdir {packages,repos,work,scratch}
[root@os1 ~]# chown -R apache.apache *
```
###  配置SELinux 使得apache可以读写 /mnt/koji
```
root@localhost$ setsebool -P allow_httpd_anon_write=1
root@localhost$ semanage fcontext -a -t public_content_rw_t "/mnt/koji(/.*)?"
root@localhost$ restorecon -r -v /mnt/koji
[root@os1 ~]# systemctl enable httpd --now
[root@os1 ~]# firewall-cmd --add-service https --permanent
[root@os1 ~]# firewall-cmd --add-service http --permanent

```

kojihub 应该可以通过 koji 命令行程序访问了。如果上面配置正确. 用 kojiadmin 的认证权限可以创建用户和设置用户权限了：

```
[root@os1 ~]# su - kojiadmin
[kojiadmin@os ~]#  koji moshimoshi #//先测试连通性

[kojiadmin@os ~]# koji add-user kojira  #// 正确返回：Added user kojira (n). 否则前面配置有问题. 解决后再继续！
[kojiadmin@os ~]# koji grant-permission repo kojira
```

注意：要用前面被配置了证书的用户(kojiadmin)执行该命令. 否则会显示“Unable to log in, no authentication methods available”

### kojiWeb 设置

```
[root@os1 ~]# yum install koji-web mod_ssl
```

编辑 /etc/kojiweb/web.conf 文件
```
[web]
SiteName = koji
#KojiTheme = mytheme

# Key urls
KojiHubURL = http://192.168.1.30/kojihub
KojiFilesURL = http://192.168.1.30/kojifiles

# Kerberos authentication options
# WebPrincipal = koji/web@EXAMPLE.COM
# WebKeytab = /etc/httpd.keytab
# WebCCache = /var/tmp/kojiweb.ccache

# SSL authentication options
WebCert = /etc/pki/koji/kojiweb.pem
ClientCA = /etc/pki/koji/ca.stplinux.com_ca_cert.crt
KojiHubCA = /etc/pki/koji/ca.stplinux.com_ca_cert.crt
WebAuthType = ssl
LoginTimeout = 72

# This must be changed and uncommented before deployment
# Secret = CHANGE_ME

LibPath = /usr/share/koji-web/lib
```

现在可以在浏览器中打开http://ip/koji/. 就可以看到koji的web页面了。

### koji Server 端相关配置（Kojira程序）

Kojira 用来创建和维护 Yum 库。需要注意：

1. Kojira 需要对目录 /mnt/koji/repos/ 具有读写权限. 建议把 Koji Server 上面的 /mnt/koji 目录挂载至 KojiBuilder 上面. 否则 Kojira 会运行失败；
2. 任何时候只允许同时运行一个 kojira 的实例；
3. 建议不要在编译机上运行 kojira . 因为编译机只需要具有目录 /mnt/koji 的只读权限就可以了。

配置文件:

* /etc/kojira/kojira.conf – Kojira 守护进程配置文件
* /etc/sysconfig/kojira – Kojira 守护进程开关

```
[root@koji ~]# yum install koji-utils createrepo
```

修改配置文件 /etc/kojira/kojira.conf

```
server=http://kojihub/kojihub
cert = /etc/pki/koji/kojira.pem
ca = /etc/pki/koji/ca.stplinux.com_ca_cert.crt
serverca = /etc/pki/koji/ca.stplinux.com_ca_cert.crt
[root@koji-server ~]$ systemctl enable kojira --now
```

请检查文件/var/log/kojira/kojira.log 确保 kojira 已经成功启动了。

需要注意的一点是 kojira 组件需要 repo 权限. 第一次运行 kojira 时系统会自动为您创建这个帐号. 但是这种方式创建的帐号没有 repo 权限. 所以您需要提前创建这个帐号并且马上赋予它 repo 权限。

```
[kojiadmin@koji-server ~]$ koji add-user kojira
[kojiadmin@koji-server ~]$ koji grant-permission repo kojira
```


## Koji Builder 配置

### 环境说明

此处假设你完成了以上的所有设置，且你的builder和koji server 不为一台机。

### 服务器端配置

#### 发送证书
```
scp /etc/pki/koji/ca.stplinux.com_ca_cert.crt root@192.168.1.31:/etc/kojid/
scp /etc/pki/koji/kojibuilder1.pem root@192.168.1.31:/etc/kojid/
```
#### 配置NFS共享
```
sudo yum install rpcbind nfs-utils
```

修改/etc/exports

```
/mnt/koji 192.168.1.31(ro,no_root_squash)
```

```
systemctl enable rpcbind nfs-server --now
```
rpcbind起不来就重启

### builder 环境设置
安装必要工具

```
[kojibuilder1@kojibuilder1 ~]$ sudo yum install epel-release && /usr/bin/crb enable && sudo yum install koji-builder createrepo
```

同时记得在/etc/hosts目录内设置好相应的解析
```
192.168.1.30 koji.qslinux.com
```
### 配置kojid
修改 /etc/kojid/kojid.conf
```
; kojihub地址
server=http://koji.qslinux.com/kojihub
; kojihub文件访问
topurl=http://koji.qslinux.com/kojifiles
;kojibuilder1证书配置
cert = /etc/kojid/kojibuilder1.pem
;koji服务器CA证书
serverca = /etc/kojid/ca.stplinux.com_ca_cert.crt
```

### 设置NFS共享客户端
```
sudo yum install nfs-utils
```

新建 /etc/systemd/system/mnt-koji.mount
```
[Unit]
Description=Koji NFS Mount
After=network.target

[Mount]
What=koji.qslinux.com:/mnt/koji
Where=/mnt/koji
Type=nfs
Options=defaults,ro

[Install]
WantedBy=multi-user.target
```
保存

```
systemctl daemon-reload
systemctl enable mnt-koji.mount --now
```

请检查你客户端是否有/mnt/koji目录。
此时执行 systemctl enable kojid --now 启动builder。



## Koji 环境初始化配置
此步骤用于初始化一个koji环境。为了之后能够顺利编译其他软件包

### 服务器配置
```
#添加host，分配活儿
su - kojiadmin
koji add-host-to-channel kojibuilder1 createrepo
koji add-host-to-channel kojibuilder1 image
koji add-host-to-channel kojibuilder1 livecd
koji add-host-to-channel kojibuilder1 livemedia

koji add-tag dist-qingsong8
koji add-tag --parent dist-qingsong8 --arches=x86_64 -x mock.yum.module_hotfixes=1 dist-qingsong8-build
koji add-target dist-qingsong8 dist-qingsong8-build dist-qingsong8

koji add-group dist-qingsong8-build build
koji add-group dist-qingsong8-build srpm-build

koji add-external-repo -m bare -t dist-qingsong8-build dist-rocky8-build-repo https://kojidev.rockylinux.org/kojifiles/repos/dist-rocky8-build/latest/x86_64/ 添加源
koji add-group-pkg dist-qingsong8-build srpm-build bash buildsys-macros-el8 git redhat-rpm-config rocky-release rpm-build scl-utils-build shadow-utils srpmproc system-release
koji add-group-pkg dist-qingsong8-build build  bash buildsys-macros-el8 bzip2 coreutils cpio diffutils findutils gawk gcc gcc-c++ git grep gzip info make module-build-macros patch redhat-rpm-config rocky-release rpm-build scl-utils-build sed shadow-utils srpmproc tar unzip util-linux which xz
koji add-pkg --owner kojiadmin dist-qingsong8 bash binutils
koji regen-repo dist-qingsong8-build
```
### koji客户端配置

修改/etc/mock/site-defaults.cfg,添加
```
config_opts['use_bootstrap_image'] = False
```



