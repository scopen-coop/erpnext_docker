SELECT DISTINCT c.cmdbash FROM ((SELECT CONCAT(
                                              'curl -X DELETE "http://0.0.0.0:6081/api/user/',personal_email,'" -H "accept: application/json";') as cmdbash
                               from tabEmployee
                               where personal_email IS NOT NULL)
                              UNION
                              (SELECT CONCAT(
                                              'curl -X DELETE "http://0.0.0.0:6081/api/user/',company_email,'" -H "accept: application/json";') as cmdbash
                               from tabEmployee
                               where company_email IS NOT NULL)
                              UNION
                              (SELECT CONCAT(
                                              'curl -X DELETE "http://0.0.0.0:6081/api/user/',email_id,'" -H "accept: application/json";') as cmdbash
                               from `tabEmail Account`
                               where email_id IS NOT NULL)
                              UNION
                              (SELECT CONCAT(
                                              'curl -X POST "http://0.0.0.0:6081/api/user" -H "accept: application/json" -H "content-type: application/json" -d \'{"email":"',
                                              personal_email, '","login":"', personal_email, '","password":"',
                                              personal_email, '"}\';') as cmdbash
                               from tabEmployee
                               where personal_email IS NOT NULL)
                              UNION
                              (SELECT CONCAT(
                                              'curl -X POST "http://0.0.0.0:6081/api/user" -H "accept: application/json" -H "content-type: application/json" -d \'{"email":"',
                                              company_email, '","login":"', company_email, '","password":"',
                                              company_email, '"}\';') as cmdbash
                               from tabEmployee
                               where company_email IS NOT NULL)
                              UNION
                              (SELECT CONCAT(
                                              'curl -X POST "http://0.0.0.0:6081/api/user" -H "accept: application/json" -H "content-type: application/json" -d \'{"email":"',
                                              email_id, '","login":"', email_id, '","password":"', email_id,
                                              '"}\';') as cmdbash
                               from `tabEmail Account`
                               where email_id IS NOT NULL)) as c
