CREATE VIEW v_decision_daily AS
SELECT
    t.`决策编号` AS `决策编号`,
    t.`提交申请时间` AS `提交申请时间`,
    t.`审批完成时间` AS `审批完成时间`,
    t.`主体` AS `主体`,
    t.`审批单名称` AS `审批单名称`,
    t.`审批类型` AS `审批类型`,
    t.`流程状态` AS `流程状态`,
    t.`申请人` AS `申请人`,
    t.`节点处理时长` AS `节点处理时长`,
    CAST(COALESCE(REGEXP_SUBSTR(t.`审批单名称`, '[0-9]+(?=[套辆台])'), '0') AS SIGNED) AS `套数`,
    CONCAT(YEAR(t.`周五日期`), '年', MONTH(t.`周五日期`), '月第',
        (FLOOR(((TO_DAYS(t.`周五日期`) - TO_DAYS(
            (CAST(CONCAT(YEAR(t.`周五日期`), '-', MONTH(t.`周五日期`), '-01') AS DATE)
            + INTERVAL (CASE DAYOFWEEK(CAST(CONCAT(YEAR(t.`周五日期`), '-', MONTH(t.`周五日期`), '-01') AS DATE))
                WHEN 1 THEN 5 WHEN 2 THEN 4 WHEN 3 THEN 3 WHEN 4 THEN 2
                WHEN 5 THEN 1 WHEN 6 THEN 0 WHEN 7 THEN 6 END) DAY)
        )) / 7)) + 1), '周') AS `年月周数`
FROM (
    SELECT
        `dpad704`.`决策编号` AS `决策编号`,
        `dpad704`.`提交申请时间` AS `提交申请时间`,
        `dpad704`.`审批完成时间` AS `审批完成时间`,
        `dpad704`.`主体` AS `主体`,
        `dpad704`.`审批单名称` AS `审批单名称`,
        `dpad704`.`审批类型` AS `审批类型`,
        `dpad704`.`流程状态` AS `流程状态`,
        `dpad704`.`申请人` AS `申请人`,
        `dpad704`.`节点处理时长` AS `节点处理时长`,
        (CASE DAYOFWEEK(`dpad704`.`提交申请时间`)
            WHEN 7 THEN (CAST(`dpad704`.`提交申请时间` AS DATE) + INTERVAL 6 DAY)
            ELSE (CAST(`dpad704`.`提交申请时间` AS DATE) + INTERVAL (6 - DAYOFWEEK(`dpad704`.`提交申请时间`)) DAY)
        END) AS `周五日期`,
        ROW_NUMBER() OVER (PARTITION BY `dpad704`.`决策编号` ORDER BY `dpad704`.`提交申请时间`) AS `rn`
    FROM `dpad704`
    WHERE `dpad704`.`提交申请时间` IS NOT NULL
        AND YEAR(`dpad704`.`提交申请时间`) = 2026
        AND `dpad704`.`审批类型` = '购入经租决策'
        AND ((NOT(`dpad704`.`审批单名称` LIKE '%三方%')) OR `dpad704`.`主体` <> '上海启源芯动力科技有限公司')
        AND (`dpad704`.`主体` = '绿电交通'
             OR `dpad704`.`审批单名称` LIKE '%购入经租%'
             OR `dpad704`.`审批单名称` LIKE '%采购经租%'
             OR `dpad704`.`审批单名称` LIKE '%经租购入%'
             OR `dpad704`.`审批单名称` LIKE '%回购经租%')
) t
WHERE t.`rn` = 1
ORDER BY t.`提交申请时间` DESC;
