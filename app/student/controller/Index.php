<?php
namespace app\student\controller;

use app\BaseController;
use think\facade\View;
use think\facade\Db;
use dh2y\qrcode\QRcode;
class Index extends BaseController
{

    public function index()
    {
		$code = new QRcode();
		$imgurl = $code->png("http://192.168.31.233:1000/index.php/student/index/login")
						->logo('smt-c.jpg')
						->getPath();
        return view('index',['imgurl'=>$imgurl]);
    }
	
	public function login()
    {
		
        return View();
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

