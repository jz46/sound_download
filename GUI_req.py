import wx
import os
from threading import Thread
# import wx.lib.pubsub.pub
from pubsub import pub
# from bs4 import BeautifulSoup
# import html2text
# from lxml import etree
import requests
import webbrowser
# import json
import wx.html
import wx.grid
import re
import win32api
import time
import queue
from lxml import etree
from xmlrpc.client import ServerProxy
import json

headers = {
    # 'User-Agent': "Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Mobile/15A372 Safari/604.1",
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36",
    'Connection': 'keep-alive'
}
# cookies = dict(customerToken='f782f8a0-6e43-11e8-9722-a7ceb2ddb814', customerId='5b1fc99a26021e4b80b09317')
q = queue.Queue()   # 实例化一个消息队列
s = ServerProxy('http://localhost:6800/rpc')
url_dict = {}
# url_file =
is_query_info = False
down_query = False            # 设置一个判断，当下载按下后，就开始下载资源。不浪费资源
wait = True
is_down = True


class DownTread:
    def __init__(self, url, path):
        self.url = url
        self.path = path
        self.num = 8
        # self.name = self.url.split('/')[-1]
        r = requests.head(self.url)
        self.total = int(r.headers['Content-Length'])
        print('total is %s' % (self.total))
        self.run()

    def run(self):
        self.fd = open(self.path, 'wb')
        thread_list = []
        n = 0
        for ran in self.get_range():
            start, end = ran
            print('thread %d start:%s,end:%s' % (n, start, end))
            n += 1
            thread = Thread(target=self.download, args=(start, end))
            thread.start()
            thread_list.append(thread)
        for i in thread_list:
            i.join()
        # print('download %s load success' % (self.name))
        self.fd.close()

    def get_range(self):
        ranges = []
        offset = int(self.total / self.num)
        for i in range(self.num):
            if i == self.num - 1:
                ranges.append((i * offset, ''))
            else:
                ranges.append((i * offset, (i + 1) * offset))
        return ranges

    def download(self, start, end):
        headers = {'Range': 'Bytes=%s-%s' % (start, end), 'Accept-Encoding': '*',
                   'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36",
                   }
        res = requests.get(self.url, headers=headers)
        print('%s:%s download success' % (start, end))
        self.fd.seek(start)
        self.fd.write(res.content)


class ParesThread:
    """用于解析资源连接"""
    def __init__(self, url, dir_path):
        # 线程实例化时立即启动
        # self.thread = thread
        self.url = url
        self.dir_path = dir_path
        self.point = 0
        # self.is_choice = is_choice
        # Thread.__init__(self)
        # self.start()
        # print(login_url, dir_path)
        self.run(url)
        # self.gid_stack = []

    def run(self, url):
        """拿到每一个page的url"""
        content = requests.get(url).content
        content = etree.HTML(content)
        end_url = content.xpath('//*[@id="vols"]/div[3]/nav/li[7]/a/@href')[0]
        print(end_url)
        self.dir_name = content.xpath('//*[@id="vols"]/div[1]/div/div/div[2]/h4/text()')[0].strip()   # 解析出资源名称
        self.dir_path = self.dir_path + '/' + self.dir_name
        if not os.path.exists(self.dir_path):
            os.makedirs(self.dir_path)

        end_page = int(re.findall('&page=(.+)', end_url)[0])

        start_page = 0
        url_id = re.findall(r'&id=(\d+)', end_url)[0]
        for i in range(start_page, end_page + 1):
            # http://liangfm.com/index.php?c=music&m=vols&id=207
            chapter_url = 'http://liangfm.com/index.php?c=music&m=vols&id=%s&page=%s' % (str(url_id), str(i))
            print(chapter_url)
            wx.CallAfter(pub.sendMessage, "update", message='资源链接解析中..请稍等' + '\n')
            self.get(chapter_url)
            # time.sleep(0.4)
        wx.CallAfter(pub.sendMessage, "update", message='!!资源链接解析完毕....' + '\n')
        self.down_url()

    def get(self, url):
        """抓取每一个page中的target url链接"""
        req = requests.session()  # 建立一个requests的session
        content = req.get(url).text
        urls = req.get('http://liangfm.com/index.php?c=music&m=item').text
        urls = json.loads(urls)
        # print(urls)
        for peer in urls:
            a_url = peer['song_path']
            song_name = peer['song_name']
            size = ''

            global url_dict
            url_dict[self.point] = {'song_name': song_name, 'a_url': a_url, 'size': size}

            with open(self.dir_path + '/' + '00' + self.dir_name + '.txt', 'a+') as f:
                # json.dump(url_dict, f, ensure_ascii=False, indent=4)
                f.write(a_url + '\n')

            self.point = self.point + 1
            wx.CallAfter(pub.sendMessage, "down_info",
                         message=song_name + '-' + str(size) + '-' + a_url + '-' + '0%')  # 传递每个文件下载
        req.close()

    def down_url(self):
        """做一个中专的作用，将下载和显示所有下载信息分开执行"""
        # for peer in url_dict:   # 将所有的下载信息都更新在UI界面上！
        #     # index = peer
        #     a_url = url_dict[peer]['a_url']
        #     song_name = url_dict[peer]['song_name']
        #     size = url_dict[peer]['size']
        #     wx.CallAfter(pub.sendMessage, "down_info", message=song_name + '-' + str(size) + '-' + a_url + '-' + '0%')  # 传递每个文件下载唯一gid
        with open(self.dir_path + '/' + '00' + self.dir_name + '.json', 'w') as f:
            json.dump(url_dict, f, ensure_ascii=False, indent=4)
            # f.write(data)
        while 1:
            if down_query:
                for peer in url_dict:     # 循环下载
                    if is_down:
                        index = peer
                        a_url = url_dict[peer]['a_url']
                        song_name = url_dict[peer]['song_name']
                        wx.CallAfter(pub.sendMessage, "update", message='开始下载%s。。。。。' % song_name + '\n')

                        self.new_name(a_url, song_name, index)

                print('下载完毕.....')
                wx.CallAfter(pub.sendMessage, "update", message='下载完毕.....' + '\n')
                break
            else:
                if wait:
                    wx.CallAfter(pub.sendMessage, "update", message='资源解析完毕，点击全部下载即可！' + '\n')
            time.sleep(3)
            global wait
            wait = False

    def new_name(self, a_url, song_name, index):
        # data = requests.get(a_url).content
        id_index = index
        num = re.findall(r'第(\d+)章', song_name.strip())  # 音频序号
        if num:
            num = num[0]
            if int(num) < 10:
                num = '000' + num
            elif int(num) < 100:
                num = '00' + num
            elif int(num) < 1000:
                num = '0' + num
            else:
                num = num
            # print(num)
        else:
            num = ''
        song_name = num + song_name + '.mp3'
        if os.path.exists(self.dir_path + '/' + song_name):
            print('!!!已存在%s' % song_name)
            wx.CallAfter(pub.sendMessage, "update", message='!!!已存在%s' % song_name + '\n')
            # h = requests.head(a_url)  # 获取资源的大小
            # size = int(h.headers['Content-Length']) / (1024 * 1000)  # 获取文件的大小
            # size = round(size, 2)
            size = 'full'
            wx.CallAfter(pub.sendMessage, "down_status", message='complete' + '-' + str(id_index) + '-' + str(size))  # 传递id
        else:
            path = self.dir_path + '/' + song_name

            h = requests.head(a_url)  # 获取资源的大小
            size = int(h.headers['Content-Length']) / (1024 * 1000)  # 获取文件的大小
            size = round(size, 1)
            wx.CallAfter(pub.sendMessage, "down_status", message='downloading' + '-' + str(id_index) + '-' + str(size))  # 传递id值表示下载完毕，更新状态！

            # DownTread(a_url, path)     # 开始进行多线程下载
            data = requests.get(headers=headers, url=a_url).content
            with open(self.dir_path + '/' + song_name, 'wb') as f:
                f.write(data)

            wx.CallAfter(pub.sendMessage, "down_status", message='complete' + '-' + str(id_index) + '-' + str(size))  # 传递id值表示下载完毕，更新状态！
            wx.CallAfter(pub.sendMessage, "update", message="资源《%s》下载成功" % song_name + '\n')  # 传递下载完成以及错误。。。

            # with open(self.dir_path + '/' + song_name, 'wb') as f:
            #     f.write(data)
        return song_name

    # wx.CallAfter(pub.sendMessage, "update", message='!!!此章节付费章节，请购买后在下载...' + '\n')

    # html = open("article.html").read().encode('utf8')


class DownInfo:
    """轮询查询aria2的每个文件的下载状态"""
    def __init__(self, down_list):
        self.down_list = down_list
        self.gid_active = []
        self.query_info()

    def query_info(self):
            time.sleep(2)


class MainWindow(wx.Frame):
    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title)
        self.SetBackgroundColour('white')
        # self.SetBackgroundStyle()
        self.icon = wx.Icon(name="./static/logo.ico", type=wx.BITMAP_TYPE_ICO)
        self.SetIcon(self.icon)

        self.point = 0    # 用于循环生成ListCtrl中的每一项
        self.down_list = []

        # 创建窗口栏
        # self.statusbar = self.CreateStatusBar()  # 创建位于窗口的底部的状态栏

        # 设置菜单
        filemenu = wx.Menu()

        # wx.ID_ABOUT和wx.ID_EXIT是wxWidgets提供的标准ID
        menuAbout = filemenu.Append(wx.ID_ABOUT, "&关于我",
                                    " Information about this program")  # (ID, 项目名称, 状态栏信息)
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        filemenu.AppendSeparator()
        menuExit = filemenu.Append(wx.ID_EXIT, "E&xit",
                                   " Terminate the program")  # (ID, 项目名称, 状态栏信息)
        self.Bind(wx.EVT_MENU, self.exit, menuExit)

        study_menu = wx.Menu()            # 创建软件使用教程的菜单栏
        study_use = study_menu.Append(wx.ID_NEW, '软件使用教程', 'use study')
        self.Bind(wx.EVT_MENU, self.study_use, study_use)
        study_menu.AppendSeparator()
        add_cookie = study_menu.Append(-1, '添加cookie', 'add cookie')
        self.Bind(wx.EVT_MENU, self.edit_cookie, add_cookie)
        # 创建顶部菜单栏
        menuBar = wx.MenuBar()
        menuBar.Append(study_menu, "&使用攻略")  # 在菜单栏中添加filemenu菜单
        menuBar.Append(filemenu, "&关于我")  # 在菜单栏中添加filemenu菜单
        self.SetMenuBar(menuBar)  # 在frame中添加菜单栏

        # 3.创建高度增强的列表显示的控件
        self.list = wx.ListCtrl(self, -1, style=wx.LC_REPORT | wx.LC_VRULES | wx.LC_HRULES, size=(640, 200))
        self.lab = ['Id', 'Title', 'Size', 'Url', 'Satus']
        i = 0
        for peer in self.lab:
            self.list.InsertColumn(i, peer)
            i = i + 1
        # self.list.InsertColumn(1, "title")
        # self.list.InsertColumn(2, "size")
        # self.list.InsertColumn(3, "url")
        # self.list.InsertColumn(4, "status")

        self.list.SetColumnWidth(0, 50)  # 设置每一列的宽度
        self.list.SetColumnWidth(1, 180)
        self.list.SetColumnWidth(2, 80)
        self.list.SetColumnWidth(3, 200)
        self.list.SetColumnWidth(4, 100)
        # i = 0
        # index = self.list.InsertItem(self.list.GetItemCount(), str(i))
        # # print(index)
        # self.list.SetItem(index, 1, 'ddd')  # 添加一列，并设置文本为data[0]
        # self.list.SetItem(index, 2, 'd449')  # 再添加一列，设置文本为data[1]
        # self.list.SetItem(index, 3, 'd449')  # 再添加一列，设置文本为data[1]

        # pub.subscribe(self.down_message, "update")  # 获取到子线程中发来的数据

        # for i in range(20):
        #     index = self.list.InsertItem(self.list.GetItemCount(), str(i))
        #     print(index)
        #     self.list.SetItem(index, 1, 'ddd')  # 添加一列，并设置文本为data[0]
        #     self.list.SetItem(index, 2, 'd449')  # 再添加一列，设置文本为data[1]

        # 创建一些Sizer
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.GridBagSizer(hgap=5, vgap=5)    # 行和列的间距是5像素
        hSizer = wx.BoxSizer(wx.VERTICAL)

        self.url = wx.StaticText(self, label='资源链接：', pos=(20, 30))
        # self.Bind(wx.EVT_MOTION, self.show_status, self.url)
        self.url_blog = wx.TextCtrl(self, pos=(100, 20), size=(420, -1))  # style=wx.TE_RICH
        # self.url_blog.SetDefaultStyle(wx.TextAttr(wx.RED))
        grid.Add(self.url, pos=(0, 0))    # 加入GridBagSizer
        grid.Add(self.url_blog, pos=(0, 1))    # 加入GridBagSizer
        self.clear_button = wx.Button(self, -1, "清除")
        grid.Add(self.clear_button, pos=(0, 2))
        self.Bind(wx.EVT_BUTTON, self.clear_url, self.clear_button)
        # self.Bind(wx.EVT_ENTER_WINDOW, self.show_status, self.clear_button)

        # 向GridBagSizer中填充空白的空间
        # grid.Add((10, 40), pos=(2, 0))

        # self.button = wx.Button(self, label='Save', pos=(200, 325))
        # self.Bind(wx.EVT_BUTTON, self.OnClick, self.button)

        self.lblname = wx.StaticText(self, label='下载路径：', pos=(20, 20))
        grid.Add(self.lblname, pos=(2, 0))
        self.dir_path = wx.TextCtrl(self, pos=(10, 10), size=(420, -1), )
        grid.Add(self.dir_path, pos=(2, 1))
        self.liulan_button = wx.Button(self, -1, "浏览")
        grid.Add(self.liulan_button, pos=(2, 2))
        self.Bind(wx.EVT_BUTTON, self.OnOpen, self.liulan_button)

        # 选择下载的格式
        # self.name_md = wx.StaticText(self, label='下载格式:', pos=(20, 20))
        # grid.Add(self.name_md, pos=(4, 0))
        # self.is_md_list = ['pdf', 'markdown', 'pdf和markdown']
        # self.is_md = wx.ComboBox(self, value='请选择下载格式', pos=wx.DefaultPosition, size=(120, 35), choices=self.is_md_list,
        #                          style=wx.CB_DROPDOWN)
        # grid.Add(self.is_md, pos=(4, 1))

        # # 向GridBagSizer中填充空白的空间
        # grid.Add((10, 20), pos=(4, 0))

        self.d_info = wx.StaticText(self, label='下载音频列表：', pos=(10, 10))
        font = wx.Font(12,  wx.ROMAN, wx.NORMAL, wx.FONTWEIGHT_BOLD)          # 设置字体大小
        self.d_info.SetFont(font)
        self.d_info.SetForegroundColour('red')           # 设置StaticText部件的文本颜色
        grid.Add(self.d_info, pos=(5, 0))
        self.logger = wx.TextCtrl(self, pos=(100, 20), size=(640, 70), style=wx.TE_MULTILINE | wx.TE_READONLY,
                                  value='下载输出信息...\n'
                                  )
        # grid.Add(self.logger, pos=(6, 0), span=(1, 3), flag=wx.BOTTOM, border=5)
        # grid.Add(self.is_md, pos=(3, 1))

        self.info = wx.Button(self, label='开始解析', pos=(10, 15))  # 总的下载按钮
        self.Bind(wx.EVT_BUTTON, self.down, self.info)

        self.down_al = wx.Button(self, label='全部下载', pos=(10, 15))  # 总的暂停下载按钮
        self.Bind(wx.EVT_BUTTON, self.down_all, self.down_al)

        self.unpuse_all = wx.Button(self, label='暂停下载', pos=(10, 15))  # 总的暂停下载按钮
        self.Bind(wx.EVT_BUTTON, self.unpuse, self.unpuse_all)

        grid2 = wx.GridBagSizer(hgap=5, vgap=5)  # 行和列的间距是5像素    # 第二个容器，用于存放下载，暂停，回复按钮

        grid2.Add(self.info, pos=(0, 2))  # span=(1, 3)
        grid2.Add(self.down_al, pos=(0, 0))
        grid2.Add(self.unpuse_all, pos=(0, 1), flag=2)
        self.speed = wx.TextCtrl(self, value='0.0M/s',
                                 size=(60, 28), style=wx.TE_CENTER | wx.TE_READONLY | wx.TE_NOHIDESEL)
        # self.wangsu = wx.StaticText(self, label="网速：", style=wx.ALIGN_CENTER, pos=(20, -3))
        # grid2.Add(self.wangsu, pos=(0, 22))
        grid2.Add(self.speed, pos=(0, 23))


        hSizer.Add(grid, 0, wx.ALL, 5)
        hSizer.Add(self.list, 0, wx.ALL, 5)
        hSizer.Add(self.logger, 0, wx.ALL, 5)
        hSizer.Add(grid2, 0, wx.ALL, 5)
        mainSizer.Add(hSizer, 0, wx.ALL, 5)
        # mainSizer.Add(self.download, 0, wx.CENTER)
        # # # mainSizer.Add(self.is_md, 0, wx.Left)
        # mainSizer.Add((20, 20))                # 添加上下空白间隔
        # mainSizer.Add(self.d_info, 0, wx.Left)
        # mainSizer.Add((20, 5))  # 添加上下空白间隔
        # mainSizer.Add(self.logger, 0, wx.CENTER)
        # 可以把SetSizer()和sizer.Fit()合并成一条SetSizerAndFit()语句
        self.SetSizerAndFit(mainSizer)

        pub.subscribe(self.down_message, "update")  # 获取到子线程中发来的数据
        pub.subscribe(self.message_list, "down_info")  # 获取到子线程中发来的下载链接信息
        pub.subscribe(self.down_status, "down_status")  # 获取到子线程2中发来的下载状态信息，

        self.timer = wx.Timer(self)   # 创建一个定时器，用于刷新speed网速控件
        self.Bind(wx.EVT_TIMER, self.show_speed, self.timer)
        # self.timer.Start(500)             # 启动定时器,100毫秒

        # text = q.get()
        # print(text)
        self.Show(True)

    def OnAbout(self, e):
        """关于我"""
        # 创建一个带"OK"按钮的对话框。wx.OK是wxWidgets提供的标准ID
        # dlg = wx.MessageDialog(self, "开发者：教主\n一个python开发者&人工智能&爬虫钟爱者...",
        #                        "关于开发者我...", wx.OK)  # 语法是(self, 内容, 标题, ID)
        # # dlg.WebSite = ("http://www.pythonlibrary.org", "My Home Page")
        # dlg.ShowModal()  # 显示对话框
        # dlg.Destroy()  # 当结束之后关闭对话框
        aboutDlg = AboutDlg(None)
        aboutDlg.Show()

    def OnOpen(self, e):
        """ 打开文件操作 """
        # wx.FileDialog语法：(self, parent, message, defaultDir, defaultFile,
        #                    wildcard, style, pos)
        dlg = wx.DirDialog(self, "Choose a file", style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            dir_path = dlg.GetPath()
            self.dir_path.SetValue(dir_path)
            # self.filename = dlg.GetFilename()
            # self.dirname = dlg.GetDirectory()
            # f = open(os.path.join(self.dirname, self.filename), 'r')  # 暂时只读
            # self.control.SetValue(f.read())
            # f.close()
        dlg.Destroy()

    def clear_url(self, event):
        """清理博客链接函数"""
        self.url_blog.SetValue('')

    def down(self, event):
        """下载博客操作"""
        # print('jgg')
        url = self.url_blog.GetValue()        # 获取课程主页链接
        # print('url %s' % url)
        dir_path = self.dir_path.GetValue()    # 获取存放文件的文件夹路径

        # is_choice = self.is_md.GetSelection()      # =-1为其他 =0 为pdf下载器，=1位markdown下载器 =2 为两种格式同时下载
        # print(type(is_choice))
        # print('dir_path %s' % dir_path)
        if url and dir_path:             # 判断路径以及博客链接是否为空
            # if is_choice == -1:
            #     alerm = wx.MessageDialog(self, "填写信息有误，下载格式未选择...", u"error!!!")
            #     alerm.ShowModal()
            # else:
            self.logger.SetValue('')  # 清空下载日志区
            t = Thread(target=ParesThread, args=(url, dir_path))
            t.setDaemon(True)     # 主线程关闭，子线程也随机关闭！
            t.start()

            # t2 = Thread(target=DownInfo, args=(self.down_list,))     # 子线程2，查询下载状态！
            # t2.setDaemon(True)  # 主线程关闭，子线程也随机关闭！
            # t2.start()

            self.timer.Start(600)  # 启动定时器,100毫秒刷新一下控件数据
        else:
            self.verify_down()
        # t.join()
        # event.GetEventObject().Disable()
        # x = TestThread()
        # event.GetEventObject().Disable()  #

    def down_message(self, message):
        """下载完成以及错误的消息！"""
        self.logger.AppendText(message)

    def verify_down(self):
        """验证是否可以下载"""
        dlg = wx.MessageDialog(self, "填写信息有误，请检查路径以及博客链接填写是否正确...", u"error!!!", wx.YES_NO | wx.ICON_QUESTION)
        # if dlg.ShowModal() == wx.ID_YES:
        #     self.Close(True)
        dlg.ShowModal()
        dlg.Destroy()

    def message_list(self, message):
        """列出所有的aria2文件下载信息"""
        # new_name + '-' + size + '-' + dir)
        mes = message.split('-')
        new_name = mes[0]
        size = mes[1] + 'M'
        url = mes[2]
        status = mes[3]
        self.down_list.append(message)   # 添加file的gid

        index = self.list.InsertItem(self.list.GetItemCount(), str(self.point))
        self.list.SetItem(index, 1, new_name)  # 添加一列，并设置文本message
        self.list.SetItem(index, 2, size)  # 添加一列，并设置文本message
        self.list.SetItem(index, 3, url)  # 再添加一列，
        self.list.SetItem(index, 4, status)  # 再添加一列，
        self.point = self.point + 1
        # self.list

    def down_status(self, message):
        message = str(message)
        message = message.split('-')
        is_complete = message[0]
        if is_complete == 'complete':
            point = int(message[1])
            size = message[2] + ' M'
            self.list.SetItem(point, 4, '100%')
            self.list.SetItem(point, 2, size)
        else:
            point = int(message[1])
            # size = message[2] + 'm'
            self.list.SetItem(point, 4, 'downloading')
            # self.list.SetItem(point, 2, size)

    def show_speed(self, e):
        """显示总的下载速度"""
        # speed = s.aria2.getGlobalStat()['downloadSpeed']
        # speed = round(float(speed) / (1024 * 1024), 1)
        # print(speed)
        speed = 10
        self.speed.SetValue(str(speed) + 'M/s')

    def down_all(self, e):
        """开始所有下载"""
        # self.timer.Stop()    # 停止定时器触发器
        # self.speed.SetValue('0.0M/s')   # 暂停下载后，将网速设置为零。
        # text = q.put('')
        global down_query
        down_query = True
        self.down_message('开始进行下载。。。')

    def unpuse(self, e):
        state = s.aria2.unpauseAll()
        self.timer.Start()    # 开启定时器触发器
        self.down_message('成功恢复下载！')
        print("成功恢复下载！")

    def exit(self, e):
        is_quit = wx.MessageDialog(None, "要退出gitchat下载器吗？", "exit", wx.YES_NO | wx.ICON_QUESTION)
        # is_quit.ShowModal()  # 显示对话框
        if is_quit.ShowModal() == wx.ID_YES:
            self.Close()
        else:
            pass
        is_quit.Destroy()  # 当结束之后关闭对话框

    # def show_status(self, e):
    #     self.statusbar.SetStatusText('25252')

    def study_use(self, e):
        webbrowser.open('https://gitee.com/pekachu/gitchat_download')

    def edit_cookie(self, e):
        path = './static/cookie.json'
        win32api.ShellExecute(0, 'open', 'notepad.exe', path, '', 1)


class AboutDlg(wx.Frame):

    def __init__(self, parent):
        wx.Frame.__init__(self, parent, wx.ID_ANY, title="关于我...", size=(400, 400))
        self.icon = wx.Icon(name="./static/logo.ico", type=wx.BITMAP_TYPE_ICO)
        self.SetIcon(self.icon)
        html = wxHTML(self)

        html.SetPage(
            ''
            "<h3>关于开发者我...</h3>"
            "<p><b>开发者：西园公子 </b></p>"
            "<p><b>一位人工智能&python&爬虫开发者...</b></p>"
            "<p>软件开源，欢迎star</p>"
            '<p><b><a href="https://github.com/jz46/gitchat_download">软件项目github地址</a></b></p>'
        )


class wxHTML(wx.html.HtmlWindow):
    def OnLinkClicked(self, link):
        webbrowser.open(link.GetHref())


app = wx.App(False)
# frame = wx.Frame(None, title="Demo with Notebook")
frame = MainWindow(None, title='Sound Downloader')

app.MainLoop()