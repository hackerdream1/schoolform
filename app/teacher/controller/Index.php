<?php
namespace app\controller;

use app\BaseController;
use think\facade\View;
use think\facade\Db;
use dh2y\qrcode\QRcode;
class Index extends BaseController
{
	protected $connection = 'connections';
    public function index()
    {
        return '<style type="text/css">*{ padding: 0; margin: 0; } div{ padding: 4px 48px;} a{color:#2E5CD5;cursor: pointer;text-decoration: none} a:hover{text-decoration:underline; } body{ background: #fff; font-family: "Century Gothic","Microsoft yahei"; color: #333;font-size:18px;} h1{ font-size: 100px; font-weight: normal; margin-bottom: 12px; } p{ line-height: 1.6em; font-size: 42px }</style><div style="padding: 24px 48px;"> <h1>:) </h1><p> ThinkPHP V' . \think\facade\App::version() . '<br/><span style="font-size:30px;">14载初心不改 - 你值得信赖的PHP框架</span></p><span style="font-size:25px;">[ V6.0 版本由 <a href="https://www.yisu.com/" target="yisu">亿速云</a> 独家赞助发布 ]</span></div><script type="text/javascript" src="https://tajs.qq.com/stats?sId=64890268" charset="UTF-8"></script><script type="text/javascript" src="https://e.topthink.com/Public/static/client.js"></script><think id="ee9b1aa918103c4fc"></think>';
    }

    public function hello($name = 'ThinkPHP6',$ccc = 'C')
    {
        return 'h222ello,' . $name . $ccc ;
    }
	
	public function aa ()
	{
		$name =  '{$name}-{$email}';
		View::assign('name','public/Thin33kPHP');
		if (\think\facade\Request::isPost()){
			echo "post：";
		}
		return View();
	}
	
	public function b()
	{
		
	
		//protected $connection = 'demo';
		$abc = \think\facade\Db::query('select * from mytable1');
		var_dump($abc);
        return "";
	}
	public function dbdbdbdbd()
	{
		$db = Db::name("mytable1") -> select();
		$code = new QRcode();
		$res = $code->png('孙睦添大笨蛋',false, 10)
			->getPath();
		echo "<img src='". $res ."' />";
		//return json($db);
		//return json($db);
	}
	
	public function c()
	{
		$data = 'Hello,ThinkPHP!';
        return download('https://www.baidu.com/img/flexible/logo/pc/result.png', 'my.jpg');
	}
}

